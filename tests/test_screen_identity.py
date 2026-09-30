"""Screen identity, page-qualified naming and frame provenance regressions."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import openpyxl
import pytest
from click.testing import CliRunner

from figma_taxonomy.cli import main
from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.extractor import extract_elements, extract_screens
from figma_taxonomy.mcp_tools import (
    export_taxonomy_tool,
    extract_taxonomy_tool,
    validate_taxonomy_tool,
)
from figma_taxonomy.models import Screen, ScreenElement
from figma_taxonomy.output.json_schema import write_json
from figma_taxonomy.taxonomy_engine import generate_taxonomy
from figma_taxonomy.validate import diff_taxonomy_dicts

FIXTURE = Path(__file__).parent / "fixtures" / "screen_identity.json"


def test_cross_page_collision_reports_pages_instead_of_merging() -> None:
    config = TaxonomyConfig()
    elements = extract_elements(json.loads(FIXTURE.read_text()), config)
    with pytest.raises(ValueError, match=r"\{page\}") as error:
        generate_taxonomy(elements, config)
    assert "Account" in str(error.value) and "Admin" in str(error.value)


def test_element_carries_page_and_frame_identity() -> None:
    elements = extract_elements(json.loads(FIXTURE.read_text()), TaxonomyConfig())
    assert [(e.page_id, e.screen_node_id) for e in elements] == [("1:0", "1:1"), ("2:0", "2:1")]


def test_pageview_sources_include_empty_variants_and_empty_screens() -> None:
    result = extract_taxonomy_tool(str(FIXTURE), page="Account")
    events = {e["event_name"]: e for e in result["events"]}
    assert events["settings_pageview"]["source_node_ids"] == ["1:1", "1:2"]
    assert events["receipt_pageview"]["source_node_ids"] == ["1:3"]
    assert events["settings_button_save_clicked"]["source_node_ids"] == ["1:11"]
    assert all(e["category"] == "Account" for e in events.values())


@pytest.mark.parametrize("style", ["snake_case", "camelCase"])
def test_page_pattern_distinguishes_flows_and_is_stable_when_filtered(
    tmp_path: Path, style: str,
) -> None:
    path = tmp_path / "naming.yaml"
    path.write_text(
        f'naming:\n  pattern: "{{page}}_{{screen}}_{{element}}_{{action}}"\n  style: {style}\n',
        encoding="utf-8",
    )
    result = extract_taxonomy_tool(str(FIXTURE), str(path))
    events = {e["event_name"]: e for e in result["events"]}
    account = "account_settings_pageview" if style == "snake_case" else "accountSettingsPageview"
    admin = "admin_settings_pageview" if style == "snake_case" else "adminSettingsPageview"
    assert events[account]["category"] == "Account"
    assert events[admin]["category"] == "Admin"
    assert events[account]["source_node_ids"] == ["1:1", "1:2"]
    assert events[admin]["source_node_ids"] == ["2:1"]
    assert len(events) == 5
    filtered = extract_taxonomy_tool(str(FIXTURE), str(path), page="Account")
    assert filtered["events"] == [e for e in result["events"] if e["category"] == "Account"]
    assert validate_taxonomy_tool(result, str(FIXTURE), str(path))["is_clean"]


def test_explicit_excluded_page_still_has_empty_screen_pageview() -> None:
    result = extract_taxonomy_tool(str(FIXTURE), page="Archive")
    assert result["count"] == 1
    assert result["events"][0]["source_node_ids"] == ["9:1"]


def test_cli_empty_screen_export_and_validation(tmp_path: Path) -> None:
    config = tmp_path / "naming.yaml"
    config.write_text('naming:\n  pattern: "{page}_{screen}_{element}_{action}"\n', encoding="utf-8")
    output = tmp_path / "out"
    runner = CliRunner()
    result = runner.invoke(main, [
        "extract", "--fixture", str(FIXTURE), "--config", str(config),
        "--output", str(output), "--format", "json",
    ])
    assert result.exit_code == 0, result.output
    stored = json.loads((output / "taxonomy.json").read_text())
    assert stored["events"]["account_receipt_pageview"]["sources"] == ["figma:node_id:1:3"]
    validation = runner.invoke(main, [
        "validate", str(output / "taxonomy.json"), "--fixture", str(FIXTURE),
        "--config", str(config), "--exit-code",
    ])
    assert validation.exit_code == 0, validation.output


def test_cli_cross_page_error_precedes_output(tmp_path: Path) -> None:
    output = tmp_path / "out"
    result = CliRunner().invoke(main, ["extract", "--fixture", str(FIXTURE), "--output", str(output)])
    assert result.exit_code == 1
    assert "{page}" in result.output
    assert not output.exists()


def _account_file() -> dict:
    tree = json.loads(FIXTURE.read_text())
    tree["document"]["children"] = tree["document"]["children"][:1]
    return tree


def _stored_events(tree: dict, tmp_path: Path) -> dict:
    config = TaxonomyConfig()
    events = generate_taxonomy(
        extract_elements(tree, config), config, screens=extract_screens(tree, config),
    )
    path = tmp_path / "taxonomy.json"
    write_json(events, config, path)
    return json.loads(path.read_text())["events"]


def test_empty_frame_rename_matches_by_source(tmp_path: Path) -> None:
    tree = _account_file()
    before = _stored_events(tree, tmp_path)
    tree["document"]["children"][0]["children"][2]["children"][0]["name"] = "Confirmation"
    report = diff_taxonomy_dicts(before, _stored_events(tree, tmp_path))
    assert report.renamed == [("receipt_pageview", "confirmation_pageview")]
    assert not report.added and not report.removed and not report.source_changes


def test_empty_variant_removal_is_source_drift(tmp_path: Path) -> None:
    tree = _account_file()
    before = _stored_events(tree, tmp_path)
    del tree["document"]["children"][0]["children"][1]
    report = diff_taxonomy_dicts(before, _stored_events(tree, tmp_path))
    assert report.source_changes == [{"event_name": "settings_pageview", "added": [], "removed": ["1:2"]}]
    assert not report.added and not report.removed


def test_flow_change_is_drift_without_renaming_events(tmp_path: Path) -> None:
    tree = _account_file()
    before = _stored_events(tree, tmp_path)
    tree["document"]["children"][0]["name"] = "Profile"
    after = _stored_events(tree, tmp_path)
    report = diff_taxonomy_dicts(before, after)
    assert not report.is_clean()
    assert not report.renamed and not report.source_changes
    assert {c["event_name"] for c in report.category_changes} == set(before)
    assert all(c["from"] == "Account" and c["to"] == "Profile" for c in report.category_changes)
    old_path = tmp_path / "old.json"
    old_path.write_text(json.dumps({"events": before}), encoding="utf-8")
    result = CliRunner().invoke(main, [
        "diff", str(old_path), str(tmp_path / "taxonomy.json"), "--exit-code",
    ])
    assert result.exit_code == 1 and "Category changes (3)" in result.output
    fixture_path = tmp_path / "renamed-page.json"
    fixture_path.write_text(json.dumps(tree), encoding="utf-8")
    mcp_report = validate_taxonomy_tool({"events": before}, str(fixture_path))
    assert not mcp_report["is_clean"]
    assert mcp_report["category_changes"] == report.category_changes
    validation = CliRunner().invoke(main, [
        "validate", str(old_path), "--fixture", str(fixture_path), "--exit-code",
    ])
    assert validation.exit_code == 1 and "Category changes (3)" in validation.output


def test_legacy_pageview_baseline_reports_added_frame_sources(tmp_path: Path) -> None:
    after = _stored_events(_account_file(), tmp_path)
    before = json.loads(json.dumps(after))
    for name, body in before.items():
        if name.endswith("_pageview"):
            body.pop("sources")
            body["source"] = ""
    report = diff_taxonomy_dicts(before, after)
    assert not report.is_clean()
    assert not report.added and not report.removed and not report.renamed
    assert {change["event_name"] for change in report.source_changes} == {
        "receipt_pageview", "settings_pageview",
    }


@pytest.mark.parametrize("other_page_name", ["Account", "Account!"])
def test_distinct_page_ids_cannot_merge_even_if_names_normalize_identically(other_page_name: str) -> None:
    tree = json.loads(FIXTURE.read_text())
    tree["document"]["children"][1]["name"] = other_page_name
    config = TaxonomyConfig()
    config.naming.pattern = "{page}_{screen}_{element}_{action}"
    with pytest.raises(ValueError, match="rename the pages"):
        generate_taxonomy(extract_elements(tree, config), config)


def test_legacy_manual_elements_keep_flow_without_fabricating_frame_ids() -> None:
    element = ScreenElement("1:11", "settings", "save", "button", None, False, parent_path=["Account"])
    events = generate_taxonomy([element], TaxonomyConfig())
    assert events[-1].event_name == "settings_pageview"
    assert events[-1].flow == "Account"
    assert events[-1].source_node_ids == []


def test_primary_pageview_source_uses_first_available_frame_id() -> None:
    events = generate_taxonomy([], TaxonomyConfig(), screens=[
        Screen("", "settings", "Account"), Screen("1:1", "settings", "Account"),
    ])
    assert len(events) == 1
    assert events[0].source_node_id == "1:1"
    assert events[0].source_node_ids == ["1:1"]


def test_control_pageview_name_collision_is_actionable() -> None:
    config = TaxonomyConfig()
    config.naming.pattern = "{screen}"
    with pytest.raises(ValueError, match=r"\{action\}"):
        generate_taxonomy(extract_elements(_account_file(), config), config)


@pytest.mark.parametrize("fmt", ["json", "csv", "markdown", "excel"])
def test_pageview_frame_sources_survive_exports(tmp_path: Path, fmt: str) -> None:
    result = extract_taxonomy_tool(str(FIXTURE), page="Account")
    path = tmp_path / ("out.xlsx" if fmt == "excel" else f"out.{fmt}")
    export_taxonomy_tool(result, fmt, str(path))
    if fmt == "json":
        event = json.loads(path.read_text())["events"]["settings_pageview"]
        assert event["source"] == "figma:node_id:1:1"
        assert event["sources"] == ["figma:node_id:1:1", "figma:node_id:1:2"]
    elif fmt == "csv":
        with path.open(encoding="utf-8", newline="") as stream:
            rows = [r for r in csv.DictReader(stream) if r["Event Type"] == "settings_pageview"]
        assert rows and all(json.loads(r["Source Node IDs"]) == ["1:1", "1:2"] for r in rows)
    elif fmt == "excel":
        workbook = openpyxl.load_workbook(path)
        rows = list(workbook["Events"].iter_rows(min_row=3, values_only=True))
        row = next(row for row in rows if row[2] == "settings_pageview")
        assert row[13] == "1:1" and json.loads(row[14]) == ["1:1", "1:2"]
        workbook.close()
    else:
        event_text = path.read_text(encoding="utf-8").split("### settings_pageview")[1]
        assert "`1:1`, `1:2`" in event_text
