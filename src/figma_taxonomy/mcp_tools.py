"""Pure-function implementations of MCP server tools.

These are separated from the MCP server wiring so they can be unit-tested
directly, and reused from the CLI or other callers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_taxonomy.config import TaxonomyConfig, load_config
from figma_taxonomy.extractor import extract_elements
from figma_taxonomy.figma_client import fetch_file, load_fixture
from figma_taxonomy.models import TaxonomyEvent
from figma_taxonomy.taxonomy_engine import generate_taxonomy
from figma_taxonomy.validate import diff_taxonomies


def _event_to_dict(event: TaxonomyEvent) -> dict[str, Any]:
    return {
        "event_name": event.event_name,
        "category": event.flow,
        "description": event.description,
        "source_node_id": event.source_node_id,
        "properties": [
            {
                "name": p.name,
                "type": p.type,
                "description": p.description,
                "enum_values": p.enum_values,
            }
            for p in event.properties
        ],
    }


def _load_figma_source(figma_url_or_path: str) -> dict:
    """Figma URL → API fetch; local path → fixture load."""
    candidate = Path(figma_url_or_path)
    if candidate.exists() and candidate.is_file():
        return load_fixture(candidate)
    return fetch_file(figma_url_or_path)


def _load_config(config_path: str | None) -> TaxonomyConfig:
    if config_path:
        return load_config(Path(config_path))
    return load_config(None)


def _filter_to_page(figma_file: dict, page_name: str) -> dict:
    document = figma_file.get("document", figma_file)
    matching = [
        child for child in document.get("children", [])
        if child.get("name") == page_name
    ]
    if not matching:
        available = [child.get("name") for child in document.get("children", [])]
        raise ValueError(f"Page '{page_name}' not found. Available: {available}")
    return {"document": {"children": matching}}


def _normalize_taxonomy(taxonomy_json: dict) -> dict:
    """Accept stored JSON or an extract-tool result without losing provenance."""
    raw_events = taxonomy_json.get("events", {})
    if isinstance(raw_events, dict):
        return taxonomy_json
    if not isinstance(raw_events, list):
        raise ValueError("events must be a stored event map or an extraction event list.")
    events: dict[str, dict] = {}
    for event in raw_events:
        name = event["event_name"]
        if name in events:
            raise ValueError(f"Duplicate event name '{name}'; resolve it before exporting node IDs.")
        node_id = event.get("source_node_id", "")
        properties: dict[str, dict] = {}
        for prop in event.get("properties", []):
            body = {"type": prop["type"], "description": prop.get("description", "")}
            if prop.get("enum_values") is not None:
                body["enum"] = prop["enum_values"]
            properties[prop["name"]] = body
        events[name] = {
            "category": event.get("category", ""),
            "description": event.get("description", ""),
            "source": f"figma:node_id:{node_id}" if node_id else "",
            "properties": properties,
        }
    return {**taxonomy_json, "events": events}


def extract_taxonomy_tool(
    figma_url_or_path: str,
    config_path: str | None = None,
    page: str | None = None,
) -> dict[str, Any]:
    """Extract a taxonomy from a Figma file or local fixture."""
    config = _load_config(config_path)
    figma_file = _load_figma_source(figma_url_or_path)

    if page:
        config.figma.exclude_pages = []
        figma_file = _filter_to_page(figma_file, page)

    elements = extract_elements(figma_file, config)
    events = generate_taxonomy(elements, config)

    return {
        "count": len(events),
        "events": [_event_to_dict(e) for e in events],
    }


def validate_taxonomy_tool(
    taxonomy_json: dict,
    figma_url_or_path: str,
    config_path: str | None = None,
) -> dict[str, Any]:
    """Diff a stored taxonomy against the current Figma file."""
    config = _load_config(config_path)
    figma_file = _load_figma_source(figma_url_or_path)

    elements = extract_elements(figma_file, config)
    current_events = generate_taxonomy(elements, config)

    existing = _normalize_taxonomy(taxonomy_json).get("events", {})
    report = diff_taxonomies(existing, current_events)

    return {
        "is_clean": report.is_clean(),
        "added": [_event_to_dict(e) for e in report.added],
        "removed": list(report.removed),
        "renamed": [{"from": old, "to": new} for old, new in report.renamed],
        "property_changes": list(report.property_changes),
    }


def export_taxonomy_tool(
    taxonomy_json: dict,
    format: str,
    output_path: str,
) -> dict[str, str]:
    """Write a taxonomy to disk in one of the supported formats."""
    fmt = format.lower()
    if fmt not in {"json", "csv", "markdown", "md", "excel", "xlsx"}:
        raise ValueError(f"Unsupported format: {format}. Use json, csv, markdown or excel.")
    taxonomy_json = _normalize_taxonomy(taxonomy_json)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        path.write_text(json.dumps(taxonomy_json, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"output_path": str(path), "format": "json"}

    # For non-JSON formats, rehydrate events and use the existing formatters.
    events = _hydrate_events(taxonomy_json.get("events", {}))
    config = TaxonomyConfig()

    if fmt == "csv":
        from figma_taxonomy.output.amplitude_csv import write_csv
        write_csv(events, config, path)
    elif fmt == "markdown" or fmt == "md":
        from figma_taxonomy.output.markdown import write_markdown
        write_markdown(events, config, path)
    elif fmt == "excel" or fmt == "xlsx":
        from figma_taxonomy.output.excel import write_excel
        write_excel(events, config, path)
    else:
        raise ValueError(f"Unsupported format: {format}")

    return {"output_path": str(path), "format": fmt}


def _hydrate_events(events_dict: dict) -> list[TaxonomyEvent]:
    from figma_taxonomy.validate import _events_from_dict
    return _events_from_dict(events_dict)
