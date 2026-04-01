"""Naming convention engine: ScreenElements → TaxonomyEvents."""

from __future__ import annotations

import fnmatch
import re

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import EventProperty, ScreenElement, TaxonomyEvent


def _to_snake_case(text: str) -> str:
    text = re.sub(r"[/\\]", "_", text)
    text = re.sub(r"([a-z])([A-Z])", r"\1_\2", text)
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text)
    return text.strip("_").lower()


def _clean_element_name(element: ScreenElement, config: TaxonomyConfig) -> str:
    if config.naming.element_name.use_text_content and element.text_content:
        return _to_snake_case(element.text_content)

    name = element.element_name
    for prefix in config.naming.element_name.strip_common:
        if name.startswith(prefix):
            name = name[len(prefix):]
            break

    return _to_snake_case(name)


def _build_event_name(
    screen: str,
    element_name: str,
    action: str,
    config: TaxonomyConfig,
) -> str:
    name = f"{screen}_{element_name}_{action}"
    name = re.sub(r"_+", "_", name).strip("_")
    if len(name) > config.naming.max_event_length:
        name = name[: config.naming.max_event_length].rstrip("_")
    return name


def _build_description(element: ScreenElement, action: str) -> str:
    text = element.text_content or element.element_name
    type_label = element.element_type

    action_descriptions = {
        "clicked": f"User clicks {text}",
        "entered": f"User enters value in {text}",
        "toggled": f"User toggles {text}",
        "checked": f"User checks {text}",
        "selected": f"User selects from {text}",
        "viewed": f"User views {text}",
        "opened": f"User opens {text}",
        "submitted": f"User submits {text}",
    }

    return action_descriptions.get(
        action, f"User interacts with {text} ({type_label})"
    )


def _get_matching_properties(
    event_name: str, config: TaxonomyConfig
) -> list[EventProperty]:
    properties: list[EventProperty] = []

    for rule in config.property_rules:
        pattern = rule["match"]
        if fnmatch.fnmatch(event_name, pattern):
            for prop_def in rule["add"]:
                properties.append(
                    EventProperty(
                        name=prop_def["name"],
                        type=prop_def.get("type", "string"),
                        description=prop_def.get("description", ""),
                        enum_values=prop_def.get("enum"),
                    )
                )

    return properties


def _get_global_properties(config: TaxonomyConfig) -> list[EventProperty]:
    return [
        EventProperty(
            name=p["name"],
            type=p.get("type", "string"),
            description=p.get("description", ""),
            enum_values=p.get("enum"),
        )
        for p in config.global_properties
    ]


def generate_taxonomy(
    elements: list[ScreenElement], config: TaxonomyConfig
) -> list[TaxonomyEvent]:
    """Generate taxonomy events from extracted screen elements.

    Creates one event per interactive element using the naming convention,
    plus one pageview event per unique screen.
    """
    events: list[TaxonomyEvent] = []
    seen_names: set[str] = set()
    screens_seen: set[str] = set()
    global_props = _get_global_properties(config)

    # Collect screen → flow mapping
    screen_flow_map: dict[str, str] = {}
    for elem in elements:
        if elem.parent_path:
            screen_flow_map[elem.screen_name] = elem.parent_path[0]

    # Generate element events
    for elem in elements:
        action = config.naming.actions.get(elem.element_type, "clicked")
        element_name = _clean_element_name(elem, config)
        event_name = _build_event_name(elem.screen_name, element_name, action, config)

        if event_name in seen_names:
            continue
        seen_names.add(event_name)
        screens_seen.add(elem.screen_name)

        rule_props = _get_matching_properties(event_name, config)

        # Deduplicate properties by name
        prop_names_seen: set[str] = set()
        all_props: list[EventProperty] = []
        for p in rule_props + global_props:
            if p.name not in prop_names_seen:
                prop_names_seen.add(p.name)
                all_props.append(p)

        flow = screen_flow_map.get(elem.screen_name, "")
        description = _build_description(elem, action)

        events.append(
            TaxonomyEvent(
                event_name=event_name,
                flow=flow,
                description=description,
                properties=all_props,
                source_node_id=elem.node_id,
            )
        )

    # Generate pageview events for each screen
    for screen_name in sorted(screens_seen):
        pv_name = f"{screen_name}_pageview"
        if pv_name not in seen_names:
            seen_names.add(pv_name)
            flow = screen_flow_map.get(screen_name, "")
            events.append(
                TaxonomyEvent(
                    event_name=pv_name,
                    flow=flow,
                    description=f"User views {screen_name.replace('_', ' ')} screen",
                    properties=list(global_props),
                    source_node_id="",
                )
            )

    return events
