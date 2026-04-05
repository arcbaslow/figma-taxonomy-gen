"""Taxonomy drift detection: diff a saved taxonomy against a freshly-extracted one."""

from __future__ import annotations

from dataclasses import dataclass, field

from figma_taxonomy.models import EventProperty, TaxonomyEvent


@dataclass
class ValidationReport:
    """Differences between a stored taxonomy and the current Figma state."""

    added: list[TaxonomyEvent] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    renamed: list[tuple[str, str]] = field(default_factory=list)
    property_changes: list[dict] = field(default_factory=list)

    def is_clean(self) -> bool:
        return not (self.added or self.removed or self.renamed or self.property_changes)


def _node_id_from_source(source: str) -> str:
    prefix = "figma:node_id:"
    return source[len(prefix):] if source.startswith(prefix) else ""


def diff_taxonomies(
    existing: dict[str, dict],
    current: list[TaxonomyEvent],
) -> ValidationReport:
    """Compare a stored taxonomy (parsed JSON "events" dict) against freshly generated events.

    Matching strategy:
    1. Try to match by Figma node_id (survives renames).
    2. Fall back to event_name for events without a node_id.
    """
    report = ValidationReport()

    existing_by_node: dict[str, tuple[str, dict]] = {}
    existing_by_name: dict[str, dict] = {}
    for name, body in existing.items():
        existing_by_name[name] = body
        node_id = _node_id_from_source(body.get("source", ""))
        if node_id:
            existing_by_node[node_id] = (name, body)

    matched_existing_names: set[str] = set()

    for event in current:
        match_name: str | None = None
        match_body: dict | None = None

        if event.source_node_id and event.source_node_id in existing_by_node:
            match_name, match_body = existing_by_node[event.source_node_id]
        elif event.event_name in existing_by_name:
            match_name = event.event_name
            match_body = existing_by_name[event.event_name]

        if match_body is None:
            report.added.append(event)
            continue

        matched_existing_names.add(match_name)

        if match_name != event.event_name:
            report.renamed.append((match_name, event.event_name))

        existing_props = set(match_body.get("properties", {}).keys())
        current_props = {p.name for p in event.properties}
        added_props = sorted(current_props - existing_props)
        removed_props = sorted(existing_props - current_props)
        if added_props or removed_props:
            report.property_changes.append(
                {
                    "event_name": event.event_name,
                    "added": added_props,
                    "removed": removed_props,
                }
            )

    for name in existing_by_name:
        if name not in matched_existing_names:
            report.removed.append(name)

    return report


def _events_from_dict(taxonomy_dict: dict[str, dict]) -> list[TaxonomyEvent]:
    """Hydrate a JSON `events` dict back into TaxonomyEvent objects for diffing."""
    events: list[TaxonomyEvent] = []
    for name, body in taxonomy_dict.items():
        node_id = _node_id_from_source(body.get("source", ""))
        props = []
        for prop_name, prop_body in (body.get("properties") or {}).items():
            props.append(
                EventProperty(
                    name=prop_name,
                    type=prop_body.get("type", "string") if isinstance(prop_body, dict) else "string",
                    description=prop_body.get("description", "") if isinstance(prop_body, dict) else "",
                    enum_values=prop_body.get("enum") if isinstance(prop_body, dict) else None,
                )
            )
        events.append(
            TaxonomyEvent(
                event_name=name,
                flow=body.get("category", ""),
                description=body.get("description", ""),
                source_node_id=node_id,
                properties=props,
            )
        )
    return events


def diff_taxonomy_dicts(
    old: dict[str, dict],
    new: dict[str, dict],
) -> ValidationReport:
    """Compare two stored taxonomies (parsed JSON `events` dicts)."""
    return diff_taxonomies(old, _events_from_dict(new))
