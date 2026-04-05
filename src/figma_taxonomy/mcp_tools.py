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
from figma_taxonomy.models import EventProperty, TaxonomyEvent
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
    return {"document": {"children": matching}}


def extract_taxonomy_tool(
    figma_url_or_path: str,
    config_path: str | None = None,
    page: str | None = None,
) -> dict[str, Any]:
    """Extract a taxonomy from a Figma file or local fixture."""
    config = _load_config(config_path)
    figma_file = _load_figma_source(figma_url_or_path)

    if page:
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

    existing = taxonomy_json.get("events", {})
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
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "json":
        path.write_text(json.dumps(taxonomy_json, indent=2, ensure_ascii=False))
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
