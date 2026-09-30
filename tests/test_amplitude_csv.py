"""Offline contract tests for the separate Amplitude Data import profile."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from figma_taxonomy.cli import main
from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.mcp_tools import (
    export_taxonomy_tool,
    extract_taxonomy_tool,
    validate_taxonomy_tool,
)
from figma_taxonomy.models import EventProperty, TaxonomyEvent
from figma_taxonomy.output.amplitude_data_csv import write_amplitude_csv

FIXTURES = Path(__file__).parent / "fixtures"


def _taxonomy() -> dict:
    return {"events": {
        "save_clicked": {
            "category": "Account", "description": 'Save "profile", café\nNext line',
            "source": "figma:node_id:1:1", "sources": ["figma:node_id:1:1", "figma:node_id:2:1"],
            "properties": {
                "mode": {"type": "string", "description": "Save mode", "enum": ["manual", "auto"]},
                "count": {"type": "integer", "description": "Count"},
                "amount": {"type": "number"},
                "enabled": {"type": "boolean"},
            },
        },
        "home_pageview": {
            "category": "Home", "description": "Home", "source": "figma:node_id:3:0", "properties": {},
        },
    }}


def test_import_contract_and_lossless_companion(tmp_path: Path) -> None:
    path = tmp_path / "plan.csv"
    result = export_taxonomy_tool(_taxonomy(), "amplitude-csv", str(path))
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        with (FIXTURES / "amplitude_data_headers.csv").open(newline="") as expected:
            assert reader.fieldnames == next(csv.reader(expected))
    assert len(rows) == 5
    assert all(row["Object type"] == "Event" and row["Property type"] == "Event Property" for row in rows)
    assert all(row["Action"] == "" and row["Event source"] == "" for row in rows)
    mode, count, amount, enabled, pageview = rows
    assert mode["Object name"] == "save_clicked" and mode["Event category"] == "Account"
    assert mode["Object description"] == _taxonomy()["events"]["save_clicked"]["description"]
    assert mode["Property value type"] == "enum" and mode["Enum values"] == "manual,auto"
    assert count["Property value type"] == "number" and count["Number is integer"] == "True"
    assert amount["Property value type"] == "number" and amount["Number is integer"] == ""
    assert enabled["Property value type"] == "boolean"
    assert pageview["Object name"] == "home_pageview" and pageview["Event property name"] == ""
    assert Path(result["companion_path"]) == tmp_path / "plan.json"
    companion = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    assert companion["events"]["save_clicked"]["sources"] == ["figma:node_id:1:1", "figma:node_id:2:1"]
    assert companion["events"]["save_clicked"]["properties"]["mode"]["enum"] == ["manual", "auto"]
    assert companion["events"]["save_clicked"]["description"] == mode["Object description"]
    assert "owner" in result["notes"].lower()


@pytest.mark.parametrize("use_config", [False, True])
def test_cli_supports_import_profile_without_changing_review_csv(tmp_path: Path, use_config: bool) -> None:
    args = ["extract", "--fixture", str(FIXTURES / "banking_app.json"), "--output", str(tmp_path / "out")]
    if use_config:
        config = tmp_path / "formats.yaml"
        config.write_text("output:\n  formats: [csv, amplitude-csv]\n", encoding="utf-8")
        args += ["--config", str(config)]
    else:
        args += ["--format", "csv,amplitude-csv"]
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0, result.output
    assert (tmp_path / "out/taxonomy.amplitude.csv").exists()
    companion = json.loads((tmp_path / "out/taxonomy.amplitude.json").read_text(encoding="utf-8"))
    assert validate_taxonomy_tool(companion, str(FIXTURES / "banking_app.json"))["is_clean"]
    assert (tmp_path / "out/taxonomy.csv").read_text().startswith("Event Type,Category,")


def test_mcp_extraction_can_export_import_profile(tmp_path: Path) -> None:
    extracted = extract_taxonomy_tool(str(FIXTURES / "variant_sources.json"))
    result = export_taxonomy_tool(extracted, "amplitude-csv", str(tmp_path / "plan.csv"))
    companion = json.loads(Path(result["companion_path"]).read_text(encoding="utf-8"))
    assert validate_taxonomy_tool(companion, str(FIXTURES / "variant_sources.json"))["is_clean"]


@pytest.mark.parametrize("schema", [
    {"type": "object"}, {"type": "array"}, {"type": "const"},
    {"type": "string", "enum": []}, {"type": "number", "enum": ["1", "2"]},
    {"type": "string", "enum": ["a,b"]}, {"type": "string", "enum": ["a\nb"]},
    {"type": "string", "enum": [" a"]}, {"type": "string", "enum": [""]},
    {"type": "string", "enum": [1]}, {"type": ["string", "null"]},
    {"type": "number", "minimum": 0}, {"type": "string", "pattern": "[a-z]+"},
])
def test_unrepresentable_schema_fails_before_writing(tmp_path: Path, schema: dict) -> None:
    taxonomy = _taxonomy()
    taxonomy["events"]["save_clicked"]["properties"]["mode"] = schema
    with pytest.raises(ValueError, match="save_clicked.*mode"):
        export_taxonomy_tool(taxonomy, "amplitude-csv", str(tmp_path / "plan.csv"))
    assert not (tmp_path / "plan.csv").exists() and not (tmp_path / "plan.json").exists()


def test_import_profile_requires_csv_extension(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\.csv"):
        export_taxonomy_tool(_taxonomy(), "amplitude-csv", str(tmp_path / "plan.json"))
    assert not (tmp_path / "plan.json").exists()


def test_shared_property_names_keep_event_specific_schemas(tmp_path: Path) -> None:
    taxonomy = _taxonomy()
    taxonomy["events"]["home_pageview"]["properties"] = {"mode": {"type": "boolean"}}
    path = tmp_path / "plan.csv"
    export_taxonomy_tool(taxonomy, "amplitude-csv", str(path))
    with path.open(newline="", encoding="utf-8") as stream:
        modes = {r["Object name"]: r["Property value type"] for r in csv.DictReader(stream)
                 if r["Event property name"] == "mode"}
    assert modes == {"save_clicked": "enum", "home_pageview": "boolean"}


def test_invalid_import_does_not_overwrite_existing_pair(tmp_path: Path) -> None:
    path = tmp_path / "plan.csv"
    path.write_text("original csv", encoding="utf-8")
    companion = path.with_suffix(".json")
    companion.write_text("original json", encoding="utf-8")
    events = [TaxonomyEvent("click", "", "", properties=[EventProperty("data", "object", "")])]
    with pytest.raises(ValueError, match="data"):
        write_amplitude_csv(events, TaxonomyConfig(), path)
    assert path.read_text() == "original csv" and companion.read_text() == "original json"


def test_cli_checks_import_schema_before_writing_other_formats(tmp_path: Path) -> None:
    config = tmp_path / "properties.yaml"
    config.write_text('global_properties:\n  - name: payload\n    type: object\n', encoding="utf-8")
    output = tmp_path / "out"
    result = CliRunner().invoke(main, [
        "extract", "--fixture", str(FIXTURES / "banking_app.json"), "--config", str(config),
        "--output", str(output), "--format", "json,csv,amplitude-csv",
    ])
    assert result.exit_code == 1 and "payload" in result.output
    assert not output.exists()


@pytest.mark.parametrize("duplicate", ["event", "property"])
def test_writer_rejects_duplicates_instead_of_losing_companion_data(tmp_path: Path, duplicate: str) -> None:
    event = TaxonomyEvent("click", "", "", [EventProperty("mode", "string", "")])
    events = [event, event] if duplicate == "event" else [event]
    if duplicate == "property":
        event.properties.append(EventProperty("mode", "boolean", ""))
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        write_amplitude_csv(events, TaxonomyConfig(), tmp_path / "plan.csv")
    assert not (tmp_path / "plan.json").exists()


def test_mcp_rejects_duplicate_extraction_properties(tmp_path: Path) -> None:
    taxonomy = {"events": [{"event_name": "save", "properties": [
        {"name": "mode", "type": "string"}, {"name": "mode", "type": "boolean"},
    ]}]}
    with pytest.raises(ValueError, match="duplicate property"):
        export_taxonomy_tool(taxonomy, "amplitude-csv", str(tmp_path / "plan.csv"))


def test_empty_taxonomy_writes_header_and_empty_companion(tmp_path: Path) -> None:
    path = tmp_path / "empty.csv"
    result = export_taxonomy_tool({"events": {}}, "amplitude-csv", str(path))
    with path.open(newline="", encoding="utf-8") as stream:
        assert len(list(csv.reader(stream))) == 1
    assert json.loads(Path(result["companion_path"]).read_text())["events"] == {}


def test_unmodeled_event_metadata_is_not_silently_dropped(tmp_path: Path) -> None:
    taxonomy = _taxonomy()
    taxonomy["events"]["save_clicked"]["required"] = ["mode"]
    with pytest.raises(ValueError, match="additional event metadata"):
        export_taxonomy_tool(taxonomy, "amplitude-csv", str(tmp_path / "plan.csv"))


@pytest.mark.parametrize("target", ["event", "property"])
def test_edited_mcp_constraints_are_not_lost_in_normalization(tmp_path: Path, target: str) -> None:
    extracted = extract_taxonomy_tool(str(FIXTURES / "variant_sources.json"))
    if target == "event":
        extracted["events"][0]["required"] = ["mode"]
    else:
        extracted["events"][0]["properties"][0]["maxLength"] = 20
    with pytest.raises(ValueError, match="unsupported"):
        export_taxonomy_tool(extracted, "amplitude-csv", str(tmp_path / "plan.csv"))
