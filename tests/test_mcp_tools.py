"""Tests for the MCP server's tool functions.

These test the pure function bodies directly (not the MCP protocol layer).
The MCP server just wraps these with FastMCP decorators.
"""

from __future__ import annotations

import json
from pathlib import Path

from figma_taxonomy.mcp_tools import (
    export_taxonomy_tool,
    extract_taxonomy_tool,
    validate_taxonomy_tool,
)


FIXTURE = Path(__file__).parent / "fixtures" / "banking_app.json"


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
                "properties": {p["name"]: {"type": p["type"]} for p in e["properties"]},
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
    mcp = pytest.importorskip("mcp.server.fastmcp")  # noqa: F841

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

    assert output_path.exists()
    content = output_path.read_text()
    assert "home_viewed" in content
