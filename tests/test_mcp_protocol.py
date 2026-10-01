"""Exercise real stdio JSON-RPC against fixture-only tools in an isolated process."""

import json
import sys
from pathlib import Path

import anyio
import pytest

pytest.importorskip("mcp")

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def _data(result) -> dict:
    assert not result.is_error, result
    return result.structured_content or json.loads(result.content[0].text)


@pytest.mark.asyncio
async def test_stdio_extract_export_validate_and_errors(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    fixture = str(root / "tests" / "fixtures" / "banking_app.json")
    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "figma_taxonomy.mcp_server"], cwd=tmp_path,
        env={"PYTHONPATH": str(root / "src"), "PYTHONUTF8": "1"},
    )
    with anyio.fail_after(45):
        async with stdio_client(parameters) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                initialized = await client.initialize()
                assert initialized.server_info.name == "figma-taxonomy-gen"
                listing = await client.list_tools()
                assert {tool.name for tool in listing.tools} == {"extract_taxonomy", "export_taxonomy", "validate_taxonomy"}
                extracted = _data(await client.call_tool("extract_taxonomy", {"figma_url_or_path": fixture, "explain": True}))
                assert extracted["count"] == 21
                assert extracted["explanation"]["schema_version"] == 1
                assert all(event["source_node_ids"] for event in extracted["events"])
                path = tmp_path / "taxonomy.json"
                _data(await client.call_tool("export_taxonomy", {"taxonomy_json": extracted, "format": "json", "output_path": str(path)}))
                stored = json.loads(path.read_text(encoding="utf-8"))
                validated = _data(await client.call_tool("validate_taxonomy", {"taxonomy_json": stored, "figma_url_or_path": fixture}))
                assert validated["is_clean"]
                extracted["events"][0]["properties"][0]["type"] = "boolean"
                changed = _data(await client.call_tool("validate_taxonomy", {"taxonomy_json": extracted, "figma_url_or_path": fixture}))
                assert changed["property_schema_changes"] and not changed["is_clean"]
                invalid = await client.call_tool("export_taxonomy", {"taxonomy_json": stored, "format": "invalid", "output_path": str(tmp_path / "bad")})
                assert invalid.is_error
                assert not (tmp_path / "bad").exists()
