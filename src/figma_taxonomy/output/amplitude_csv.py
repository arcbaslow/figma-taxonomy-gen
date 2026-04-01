"""Amplitude Data CSV output formatter."""

from __future__ import annotations

import csv
from pathlib import Path

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import TaxonomyEvent


def write_csv(
    events: list[TaxonomyEvent],
    config: TaxonomyConfig,
    output_path: Path,
) -> None:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Event Type", "Category", "Description",
            "Property Name", "Property Type", "Property Description",
        ])

        for event in events:
            if event.properties:
                for prop in event.properties:
                    writer.writerow([
                        event.event_name, event.flow, event.description,
                        prop.name, prop.type, prop.description,
                    ])
            else:
                writer.writerow([
                    event.event_name, event.flow, event.description,
                    "", "", "",
                ])
