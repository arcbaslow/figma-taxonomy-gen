"""Amplitude Data import CSV plus a mandatory provenance-preserving JSON companion.

Contract: https://amplitude.com/docs/data/csv-import-export (2026-09-30).
The review CSV remains a separate format. No remote requests are made here.
"""

from __future__ import annotations

import csv
from pathlib import Path

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import EventProperty, TaxonomyEvent
from figma_taxonomy.output.json_schema import write_json

IMPORT_HEADERS = (
    "Action", "Array min items", "Array max items", "Array unique items", "Const value",
    "Enum values", "Event activity", "Event hidden from dropdowns",
    "Event hidden from persona results", "Event hidden from pathfinder", "Event hidden from timeline",
    "Event category", "Event display name", "Event property name", "Event source",
    "Number property value min", "Number property value max", "Number is integer",
    "Object type", "Object name", "Object owner", "Object description", "Property type",
    "Property group names", "Property description", "Property value type", "Property required",
    "Property visibility", "Property is array", "Property regex", "String property value min length",
    "String property value max length", "Tags",
)

IMPORT_NOTES = (
    "Review Amplitude's import branch before merging. Blank Object owner clears existing owners; "
    "this profile does not preserve remote metadata. Keep the JSON companion for Figma sources."
)


def _property_fields(event_name: str, prop: EventProperty) -> dict[str, str]:
    context = f"Event '{event_name}', property '{prop.name}'"
    if not isinstance(prop.name, str) or not prop.name.strip():
        raise ValueError(f"{context}: provide a non-empty property name for amplitude-csv.")
    if not isinstance(prop.type, str) or prop.type not in {
        "string", "number", "integer", "boolean", "any", "enum",
    }:
        raise ValueError(
            f"{context}: type '{prop.type}' is not supported by amplitude-csv. "
            "Use string, number, integer, boolean, any, or a string enum; retain other schemas in JSON."
        )
    fields = {
        "Event property name": prop.name,
        "Property description": prop.description,
        "Property value type": "number" if prop.type == "integer" else prop.type,
        "Number is integer": "True" if prop.type == "integer" else "",
    }
    if prop.enum_values is not None or prop.type == "enum":
        values = prop.enum_values
        if prop.type not in {"string", "enum"} or not isinstance(values, list) or not values:
            raise ValueError(f"{context}: amplitude-csv requires a non-empty string enum.")
        if any(
            not isinstance(value, str) or not value or value != value.strip()
            or any(char in value for char in ",\r\n")
            for value in values
        ):
            raise ValueError(
                f"{context}: enum values must be non-empty strings without commas, line breaks, "
                "or surrounding whitespace. Amplitude's CSV list has no documented escaping; "
                "revise the enum or use JSON to preserve it."
            )
        fields["Property value type"] = "enum"
        fields["Enum values"] = ",".join(values)
    return fields


def build_import_rows(events: list[TaxonomyEvent]) -> list[dict[str, str]]:
    """Validate the entire plan before writing; properties remain scoped to events."""
    rows: list[dict[str, str]] = []
    event_names: set[str] = set()
    for event in events:
        if not isinstance(event.event_name, str) or not event.event_name.strip():
            raise ValueError("amplitude-csv requires non-empty event names.")
        if event.event_name in event_names:
            raise ValueError(f"Duplicate event '{event.event_name}'; merge its sources before exporting.")
        event_names.add(event.event_name)
        base = {
            "Object type": "Event", "Object name": event.event_name,
            "Object description": event.description, "Event category": event.flow,
            "Property type": "Event Property",
        }
        property_names: set[str] = set()
        for prop in event.properties:
            fields = _property_fields(event.event_name, prop)
            if prop.name in property_names:
                raise ValueError(f"Event '{event.event_name}': duplicate property '{prop.name}'.")
            property_names.add(prop.name)
            rows.append({**base, **fields})
        if not event.properties:
            rows.append(base)
    return rows


def validate_stored_schema(events: dict[str, dict]) -> None:
    """Reject unsupported fields before model hydration can discard their meaning."""
    event_fields = {"category", "description", "source", "sources", "properties"}
    property_fields = {"type", "description", "enum"}
    for name, body in events.items():
        if not isinstance(body, dict) or set(body) - event_fields:
            raise ValueError(
                f"Event '{name}': amplitude-csv accepts category, description, source(s), and properties. "
                "Use JSON for additional event metadata."
            )
        properties = body.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError(f"Event '{name}': properties must be a schema map for amplitude-csv.")
        for prop_name, schema in properties.items():
            if not isinstance(schema, dict) or set(schema) - property_fields:
                raise ValueError(
                    f"Event '{name}', property '{prop_name}': amplitude-csv accepts type, description, "
                    "and enum only. Use JSON to preserve other constraints."
                )


def validate_extraction_schema(events: list[dict]) -> None:
    """Prevent edited MCP extraction results from losing unmodeled constraints."""
    event_fields = {
        "event_name", "category", "description", "source_node_id", "source_node_ids", "properties",
    }
    property_fields = {"name", "type", "description", "enum_values"}
    for event in events:
        name = event.get("event_name", "")
        if set(event) - event_fields:
            raise ValueError(f"Event '{name}': unsupported metadata for amplitude-csv; use JSON.")
        for prop in event.get("properties", []):
            if set(prop) - property_fields:
                raise ValueError(
                    f"Event '{name}', property '{prop.get('name', '')}': "
                    "unsupported constraints for amplitude-csv; use JSON."
                )


def write_amplitude_csv(
    events: list[TaxonomyEvent], config: TaxonomyConfig, output_path: Path,
) -> Path:
    """Write the 33-column import and a sibling .json retaining schemas and IDs."""
    if output_path.suffix.lower() != ".csv":
        raise ValueError("amplitude-csv output_path must end in .csv; its companion uses .json.")
    rows = build_import_rows(events)
    companion_path = output_path.with_suffix(".json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(events, config, companion_path)
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=IMPORT_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return companion_path
