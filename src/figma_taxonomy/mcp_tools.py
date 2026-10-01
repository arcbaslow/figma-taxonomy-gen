"""Pure-function implementations of MCP server tools.

These are separated from the MCP server wiring so they can be unit-tested
directly, and reused from the CLI or other callers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from figma_taxonomy.config import TaxonomyConfig, load_config
from figma_taxonomy.extractor import explain_detection, extract_elements, extract_screens
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
        "source_node_ids": list(event.source_node_ids),
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


def _load_figma_source(figma_url_or_path: str, **fetch_options: Any) -> dict:
    """Figma URL → API fetch; local path → fixture load."""
    candidate = Path(figma_url_or_path)
    if candidate.exists() and candidate.is_file():
        return load_fixture(candidate)
    return fetch_file(figma_url_or_path, **fetch_options)


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
        node_ids = list(dict.fromkeys(
            node for node in [node_id, *event.get("source_node_ids", [])] if node
        ))
        node_id = node_ids[0] if node_ids else ""
        properties: dict[str, dict] = {}
        for prop in event.get("properties", []):
            if prop["name"] in properties:
                raise ValueError(f"Event '{name}': duplicate property '{prop['name']}'.")
            body = {"type": prop["type"], "description": prop.get("description", "")}
            if prop.get("enum_values") is not None:
                body["enum"] = prop["enum_values"]
            properties[prop["name"]] = body
        events[name] = {
            "category": event.get("category", ""),
            "description": event.get("description", ""),
            "source": f"figma:node_id:{node_id}" if node_id else "",
            "sources": [f"figma:node_id:{node}" for node in node_ids],
            "properties": properties,
        }
    return {**taxonomy_json, "events": events}


def extract_taxonomy_tool(
    figma_url_or_path: str,
    config_path: str | None = None,
    page: str | None = None,
    *, cache_ttl: float = 300, offline: bool = False, no_cache: bool = False,
    explain: bool = False,
) -> dict[str, Any]:
    """Extract a taxonomy from a Figma file or local fixture."""
    config = _load_config(config_path)
    figma_file = _load_figma_source(figma_url_or_path, cache_ttl=cache_ttl, offline=offline, no_cache=no_cache)

    if page:
        config.figma.exclude_pages = []
        figma_file = _filter_to_page(figma_file, page)

    elements = extract_elements(figma_file, config)
    events = generate_taxonomy(elements, config, screens=extract_screens(figma_file, config))

    result = {
        "count": len(events),
        "events": [_event_to_dict(e) for e in events],
    }
    if explain:
        result["explanation"] = explain_detection(figma_file, config, events)
    return result


def validate_taxonomy_tool(
    taxonomy_json: dict,
    figma_url_or_path: str,
    config_path: str | None = None,
    *, cache_ttl: float = 0, offline: bool = False, no_cache: bool = False,
) -> dict[str, Any]:
    """Diff a stored taxonomy against the current Figma file."""
    config = _load_config(config_path)
    figma_file = _load_figma_source(figma_url_or_path, cache_ttl=cache_ttl, offline=offline, no_cache=no_cache)

    elements = extract_elements(figma_file, config)
    current_events = generate_taxonomy(elements, config, screens=extract_screens(figma_file, config))

    existing = _normalize_taxonomy(taxonomy_json).get("events", {})
    report = diff_taxonomies(existing, current_events)

    return {
        "is_clean": report.is_clean(),
        "added": [_event_to_dict(e) for e in report.added],
        "removed": list(report.removed),
        "renamed": [{"from": old, "to": new} for old, new in report.renamed],
        "property_changes": list(report.property_changes),
        "source_changes": list(report.source_changes),
        "category_changes": list(report.category_changes),
        "property_schema_changes": list(report.property_schema_changes),
    }


def export_taxonomy_tool(
    taxonomy_json: dict,
    format: str,
    output_path: str,
) -> dict[str, str]:
    """Write a taxonomy to disk in one of the supported formats."""
    fmt = format.lower()
    if fmt not in {"json", "csv", "markdown", "md", "excel", "xlsx", "amplitude-csv"}:
        raise ValueError(f"Unsupported format: {format}. Use json, csv, markdown, excel or amplitude-csv.")
    if fmt == "amplitude-csv" and isinstance(taxonomy_json.get("events"), list):
        from figma_taxonomy.output.amplitude_data_csv import validate_extraction_schema
        validate_extraction_schema(taxonomy_json["events"])
    taxonomy_json = _normalize_taxonomy(taxonomy_json)
    path = Path(output_path)

    if fmt == "amplitude-csv":
        from figma_taxonomy.output.amplitude_data_csv import (
            IMPORT_NOTES,
            validate_stored_schema,
            write_amplitude_csv,
        )
        validate_stored_schema(taxonomy_json.get("events", {}))
        events = _hydrate_events(taxonomy_json.get("events", {}))
        companion_path = write_amplitude_csv(events, TaxonomyConfig(), path)
        return {
            "output_path": str(path), "format": fmt,
            "companion_path": str(companion_path), "notes": IMPORT_NOTES,
        }

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
