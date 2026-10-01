"""Property-schema changes must reach Python, CLI and MCP drift reports."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from click.testing import CliRunner

from figma_taxonomy.cli import main
from figma_taxonomy.mcp_tools import extract_taxonomy_tool, validate_taxonomy_tool
from figma_taxonomy.validate import diff_taxonomy_dicts


def _plan(schema: dict) -> dict:
    return {"pay": {"source": "figma:node_id:1:1", "properties": {"amount": schema}}}


@pytest.mark.parametrize("before,after,field", [
    ({"type": "number"}, {"type": "string"}, "type"),
    ({"enum": ["cash", "card"]}, {"enum": ["card"]}, "enum"),
    ({}, {"enum": ["card"]}, "enum"),
    ({"enum": ["card"]}, {}, "enum"),
    ({"description": "Old"}, {"description": "New"}, "description"),
    ({"minimum": 0}, {"minimum": 1}, "minimum"),
])
def test_schema_change_is_drift(before: dict, after: dict, field: str) -> None:
    report = diff_taxonomy_dicts(_plan(before), _plan(after))
    assert not report.is_clean()
    assert not report.property_changes
    assert report.property_schema_changes[0]["event_name"] == "pay"
    assert report.property_schema_changes[0]["property"] == "amount"
    assert field in report.property_schema_changes[0]["changes"]


def test_enum_order_duplicates_and_legacy_defaults_do_not_drift() -> None:
    before = _plan({"enum": ["cash", "card", "card"]})
    after = _plan({"type": "string", "description": "", "enum": ["card", "cash"]})
    original = deepcopy(before)
    assert diff_taxonomy_dicts(before, after).is_clean()
    assert before == original


def test_schema_changes_follow_renames_and_keep_additions_separate() -> None:
    before = _plan({"type": "number"})
    after = {"purchase": _plan({"type": "string"})["pay"]}
    after["purchase"]["properties"]["currency"] = {"type": "string"}
    report = diff_taxonomy_dicts(before, after)
    assert report.renamed == [("pay", "purchase")]
    assert report.property_changes[0]["added"] == ["currency"]
    assert report.property_schema_changes[0]["event_name"] == "purchase"


def test_cli_diff_reports_schema_only_changes(tmp_path: Path) -> None:
    paths = [tmp_path / "old.json", tmp_path / "new.json"]
    for path, kind in zip(paths, ["number", "string"]):
        path.write_text(json.dumps({"events": _plan({"type": kind})}), encoding="utf-8")
    result = CliRunner().invoke(main, ["diff", *map(str, paths), "--exit-code"])
    assert result.exit_code == 1
    assert "Property schema changes" in result.output
    assert "amount" in result.output and "number" in result.output and "string" in result.output


def test_mcp_and_cli_validate_report_schema_only_changes(tmp_path: Path) -> None:
    fixture = str(Path(__file__).parent / "fixtures" / "banking_app.json")
    extracted = extract_taxonomy_tool(fixture)
    extracted["events"][0]["properties"][0]["type"] = "boolean"
    report = validate_taxonomy_tool(extracted, fixture)
    assert not report["is_clean"]
    assert report["property_schema_changes"][0]["changes"]["type"]["from"] == "boolean"
    from figma_taxonomy.mcp_tools import _normalize_taxonomy
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps(_normalize_taxonomy(extracted)), encoding="utf-8")
    result = CliRunner().invoke(main, ["validate", str(path), "--fixture", fixture, "--exit-code"])
    assert result.exit_code == 1 and "Property schema changes" in result.output
