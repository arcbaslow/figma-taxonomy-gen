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
    source_changes: list[dict] = field(default_factory=list)
    category_changes: list[dict] = field(default_factory=list)

    def is_clean(self) -> bool:
        return not (
            self.added or self.removed or self.renamed or self.property_changes
            or self.source_changes or self.category_changes
        )


def _node_id_from_source(source: str) -> str:
    prefix = "figma:node_id:"
    return source[len(prefix):] if source.startswith(prefix) else ""


def _source_node_ids(body: dict) -> list[str]:
    """Read additive sources and the primary source from older saved taxonomies."""
    return list(dict.fromkeys(
        node for source in [body.get("source", ""), *body.get("sources", [])]
        if (node := _node_id_from_source(source))
    ))


def diff_taxonomies(
    existing: dict[str, dict],
    current: list[TaxonomyEvent],
) -> ValidationReport:
    """Compare a stored taxonomy (parsed JSON "events" dict) against freshly generated events.

    Matching strategy:
    1. Match shared Figma sources only when the correspondence is one-to-one.
    2. Fall back to unchanged event names for unmatched events.
    Splits and merges with ambiguous identities are additions/removals, not renames.
    """
    report = ValidationReport()

    old_sources = {name: set(_source_node_ids(body)) for name, body in existing.items()}
    existing_by_node: dict[str, set[str]] = {}
    for name, nodes in old_sources.items():
        for node in nodes:
            existing_by_node.setdefault(node, set()).add(name)
    candidates: dict[str, set[str]] = {}
    reverse: dict[str, set[str]] = {}
    for event in current:
        names: set[str] = set()
        for node in event.source_node_ids:
            names.update(existing_by_node.get(node, set()))
        candidates[event.event_name] = names
        for name in names:
            reverse.setdefault(name, set()).add(event.event_name)

    matches: dict[str, str] = {}
    for name, options in candidates.items():
        if len(options) == 1:
            old_name = next(iter(options))
            if len(reverse[old_name]) == 1:
                matches[name] = old_name
    matched_existing_names = set(matches.values())
    for event in current:
        name = event.event_name
        if name not in matches and name in existing and name not in matched_existing_names:
            matches[name] = name
            matched_existing_names.add(name)

    for event in current:
        match_name = matches.get(event.event_name)
        if match_name is None:
            report.added.append(event)
            continue
        match_body = existing[match_name]

        if match_name != event.event_name:
            report.renamed.append((match_name, event.event_name))

        old_category = match_body.get("category", "")
        if old_category != event.flow:
            report.category_changes.append({
                "event_name": event.event_name, "from": old_category, "to": event.flow,
            })

        current_sources = set(event.source_node_ids)
        added_sources = sorted(current_sources - old_sources[match_name])
        removed_sources = sorted(old_sources[match_name] - current_sources)
        if added_sources or removed_sources:
            report.source_changes.append({
                "event_name": event.event_name,
                "added": added_sources,
                "removed": removed_sources,
            })

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

    for name in existing:
        if name not in matched_existing_names:
            report.removed.append(name)

    return report


def _events_from_dict(taxonomy_dict: dict[str, dict]) -> list[TaxonomyEvent]:
    """Hydrate a JSON `events` dict back into TaxonomyEvent objects for diffing."""
    events: list[TaxonomyEvent] = []
    for name, body in taxonomy_dict.items():
        node_ids = _source_node_ids(body)
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
                source_node_ids=node_ids,
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
