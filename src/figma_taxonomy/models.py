"""Core data models for the figma-taxonomy pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScreenElement:
    """An interactive UI element extracted from a Figma file."""

    node_id: str
    screen_name: str
    element_name: str
    element_type: str
    text_content: str | None
    has_interaction: bool
    variants: list[str] = field(default_factory=list)
    parent_path: list[str] = field(default_factory=list)


@dataclass
class EventProperty:
    """A property attached to a taxonomy event."""

    name: str
    type: str
    description: str
    enum_values: list[str] | None = None


@dataclass
class TaxonomyEvent:
    """A generated analytics event in the taxonomy."""

    event_name: str
    flow: str
    description: str
    properties: list[EventProperty] = field(default_factory=list)
    source_node_id: str = ""
