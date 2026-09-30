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
    page_id: str = ""
    screen_node_id: str = ""


@dataclass
class Screen:
    """A Figma screen frame, whether or not it contains interactive controls."""

    node_id: str
    screen_name: str
    page_name: str
    page_id: str = ""


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
    source_node_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Keep the legacy primary source while retaining every contributing node."""
        self.source_node_ids = list(dict.fromkeys(
            node for node in [self.source_node_id, *self.source_node_ids] if node
        ))
        self.source_node_id = self.source_node_ids[0] if self.source_node_ids else ""
