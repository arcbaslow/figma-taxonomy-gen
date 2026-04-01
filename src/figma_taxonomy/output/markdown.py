"""Markdown tracking plan output formatter."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import TaxonomyEvent


def write_markdown(
    events: list[TaxonomyEvent],
    config: TaxonomyConfig,
    output_path: Path,
) -> None:
    flows: dict[str, list[TaxonomyEvent]] = defaultdict(list)
    for event in events:
        flows[event.flow or "Other"].append(event)

    lines = [f"# {config.app.name} — Event Taxonomy", ""]

    for flow_name, flow_events in flows.items():
        lines.append(f"## {flow_name}")
        lines.append("")

        for event in flow_events:
            lines.append(f"### {event.event_name}")
            lines.append(f"- **Trigger:** {event.description}")
            if event.source_node_id:
                lines.append(f"- **Source:** Figma node `{event.source_node_id}`")

            if event.properties:
                lines.append("- **Properties:**")
                for prop in event.properties:
                    desc = f" — {prop.description}" if prop.description else ""
                    enum_str = ""
                    if prop.enum_values:
                        enum_str = f" (enum: {', '.join(prop.enum_values)})"
                    lines.append(f"  - `{prop.name}` ({prop.type}){desc}{enum_str}")
            else:
                lines.append("- **Properties:** none")

            lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
