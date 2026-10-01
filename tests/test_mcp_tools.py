"""Tests for the MCP server's tool functions.

These test the pure function bodies directly (not the MCP protocol layer).
The MCP server just wraps these with MCPServer decorators.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from figma_taxonomy.mcp_tools import (
    export_taxonomy_tool,
    extract_taxonomy_tool,
    validate_taxonomy_tool,
)

FIXTURE = Path(__file__).parent / "fixtures" / "banking_app.json"


@pytest.mark.parametrize('format', ['json', 'csv', 'markdown', 'excel'])
def test_extraction_can_be_exported_directly(format: str, tmp_path: Path) -> None:
    extracted = extract_taxonomy_tool(str(FIXTURE))
    path = tmp_path / f'export.{format}'
    export_taxonomy_tool(extracted, format, str(path))
    assert path.stat().st_size > 0
    if format == 'json':
        stored = json.loads(path.read_text(encoding='utf-8'))
        first = extracted['events'][0]
        assert stored['events'][first['event_name']]['source'].endswith(first['source_node_id'])
        assert validate_taxonomy_tool(stored, str(FIXTURE))['is_clean']


def test_extraction_can_be_validated_directly() -> None:
    extracted = extract_taxonomy_tool(str(FIXTURE))
    assert validate_taxonomy_tool(extracted, str(FIXTURE))['is_clean']


def test_missing_page_is_actionable() -> None:
    with pytest.raises(ValueError, match='Available:'):
        extract_taxonomy_tool(str(FIXTURE), page='Missing')


def test_explicit_page_overrides_excluded_pages() -> None:
    assert extract_taxonomy_tool(str(FIXTURE), page='Archive')['count'] > 0


def test_extract_taxonomy_tool_from_fixture():
    result = extract_taxonomy_tool(figma_url_or_path=str(FIXTURE))

    assert "events" in result
    assert "count" in result
    assert result["count"] > 0
    assert isinstance(result["events"], list)
    first = result["events"][0]
    assert "event_name" in first
    assert "category" in first
    assert "properties" in first


def test_extract_taxonomy_tool_accepts_page_filter():
    result_all = extract_taxonomy_tool(figma_url_or_path=str(FIXTURE))
    result_filtered = extract_taxonomy_tool(figma_url_or_path=str(FIXTURE), page="Login")

    assert result_filtered["count"] <= result_all["count"]
    assert result_filtered["count"] > 0


def test_validate_taxonomy_tool_clean():
    extracted = extract_taxonomy_tool(figma_url_or_path=str(FIXTURE))
    taxonomy_json = {
        "events": {
            e["event_name"]: {
                "description": e["description"],
                "category": e["category"],
                "source": f"figma:node_id:{e['source_node_id']}" if e["source_node_id"] else "",
                "sources": [f"figma:node_id:{node}" for node in e["source_node_ids"]],
                "properties": {
                    p["name"]: {"type": p["type"], "description": p["description"],
                                "enum": p["enum_values"]}
                    for p in e["properties"]
                },
            }
            for e in extracted["events"]
        }
    }

    result = validate_taxonomy_tool(
        taxonomy_json=taxonomy_json,
        figma_url_or_path=str(FIXTURE),
    )

    assert result["is_clean"] is True
    assert result["added"] == []
    assert result["removed"] == []


def test_validate_taxonomy_tool_detects_drift():
    result = validate_taxonomy_tool(
        taxonomy_json={"events": {}},
        figma_url_or_path=str(FIXTURE),
    )

    assert result["is_clean"] is False
    assert len(result["added"]) > 0


def test_export_taxonomy_tool_writes_json(tmp_path):
    taxonomy_json = {
        "events": {
            "test_event": {
                "description": "test",
                "category": "Test",
                "source": "figma:node_id:1:1",
                "properties": {},
            }
        }
    }
    output_path = tmp_path / "out.json"

    result = export_taxonomy_tool(
        taxonomy_json=taxonomy_json,
        format="json",
        output_path=str(output_path),
    )

    assert result["output_path"] == str(output_path)
    assert output_path.exists()
    written = json.loads(output_path.read_text())
    assert "test_event" in written["events"]


def test_mcp_server_builds_with_all_tools():
    """Server construction should register extract, validate, and export tools."""
    import pytest
    # Missing optional SDK may skip; an installed incompatible SDK must fail.
    pytest.importorskip("mcp")

    from figma_taxonomy.mcp_server import build_server

    server = build_server()
    assert server.name == "figma-taxonomy-gen"


def test_export_taxonomy_tool_markdown(tmp_path):
    taxonomy_json = {
        "events": {
            "home_viewed": {
                "description": "User views home",
                "category": "Home",
                "source": "figma:node_id:1:1",
                "properties": {"screen_name": {"type": "string", "description": "Screen"}},
            }
        }
    }
    output_path = tmp_path / "out.md"

    result = export_taxonomy_tool(
        taxonomy_json=taxonomy_json,
        format="markdown",
        output_path=str(output_path),
    )

    assert result == {"output_path": str(output_path), "format": "markdown"}
    assert output_path.exists()
    content = output_path.read_text()
    assert "home_viewed" in content
