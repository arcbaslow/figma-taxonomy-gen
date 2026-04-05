"""MCP server exposing figma-taxonomy-gen tools to Claude Desktop / claude.ai.

Run with: python -m figma_taxonomy.mcp_server
(or via the console script: figma-taxonomy-mcp)

Tools exposed:
  - extract_taxonomy(figma_url_or_path, config_path?, page?)
  - validate_taxonomy(taxonomy_json, figma_url_or_path, config_path?)
  - export_taxonomy(taxonomy_json, format, output_path)
"""

from __future__ import annotations

from typing import Any

from figma_taxonomy.mcp_tools import (
    export_taxonomy_tool,
    extract_taxonomy_tool,
    validate_taxonomy_tool,
)


def build_server():
    """Construct and configure the MCP server. Kept as a function for testability."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        raise ImportError(
            "MCP server requires the 'mcp' package. "
            "Install with: uv pip install 'figma-taxonomy-gen[mcp]'"
        ) from e

    mcp = FastMCP("figma-taxonomy-gen")

    @mcp.tool()
    def extract_taxonomy(
        figma_url_or_path: str,
        config_path: str | None = None,
        page: str | None = None,
    ) -> dict[str, Any]:
        """Extract an Amplitude taxonomy from a Figma file.

        Args:
            figma_url_or_path: Figma file URL, file key, or path to a local JSON fixture.
            config_path: Optional path to a taxonomy.config.yaml.
            page: Optional page name to restrict extraction to.

        Returns:
            {"count": int, "events": [ {event_name, category, description, ...} ]}
        """
        return extract_taxonomy_tool(figma_url_or_path, config_path, page)

    @mcp.tool()
    def validate_taxonomy(
        taxonomy_json: dict,
        figma_url_or_path: str,
        config_path: str | None = None,
    ) -> dict[str, Any]:
        """Diff a stored taxonomy JSON against the current Figma file.

        Args:
            taxonomy_json: Parsed taxonomy JSON (must contain an "events" key).
            figma_url_or_path: Figma URL or path to local fixture.
            config_path: Optional path to a taxonomy.config.yaml.

        Returns:
            {"is_clean": bool, "added": [...], "removed": [...], "renamed": [...],
             "property_changes": [...]}
        """
        return validate_taxonomy_tool(taxonomy_json, figma_url_or_path, config_path)

    @mcp.tool()
    def export_taxonomy(
        taxonomy_json: dict,
        format: str,
        output_path: str,
    ) -> dict[str, str]:
        """Write a taxonomy to disk in one of: json, csv, markdown, excel.

        Args:
            taxonomy_json: Parsed taxonomy JSON.
            format: Output format - json | csv | markdown | excel.
            output_path: Destination file path.

        Returns:
            {"output_path": str, "format": str}
        """
        return export_taxonomy_tool(taxonomy_json, format, output_path)

    return mcp


def main():
    server = build_server()
    server.run()


if __name__ == "__main__":
    main()
