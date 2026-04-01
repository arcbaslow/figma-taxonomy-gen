"""JSON Schema output formatter."""

from __future__ import annotations

import json
from pathlib import Path

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import TaxonomyEvent


def write_json(
    events: list[TaxonomyEvent],
    config: TaxonomyConfig,
    output_path: Path,
) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"{config.app.name} Event Taxonomy",
        "events": {},
    }

    for event in events:
        properties = {}
        for prop in event.properties:
            prop_schema: dict = {"type": prop.type, "description": prop.description}
            if prop.enum_values:
                prop_schema["enum"] = prop.enum_values
            properties[prop.name] = prop_schema

        schema["events"][event.event_name] = {
            "description": event.description,
            "category": event.flow,
            "source": f"figma:node_id:{event.source_node_id}" if event.source_node_id else "",
            "properties": properties,
        }

    output_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False))
