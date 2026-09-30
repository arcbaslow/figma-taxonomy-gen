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
    *,
    truncate: bool = True,
) -> str:
    if config.naming.max_event_length <= 0:
        raise ValueError("naming.max_event_length must be a positive integer.")
    try:
        name = config.naming.pattern.format(screen=screen, element=element_name, action=action)
    except (KeyError, ValueError, IndexError, AttributeError) as exc:
        raise ValueError(
            "naming.pattern must use {screen}, {element} and/or {action} placeholders."
        ) from exc
    name = _to_snake_case(name)
    if config.naming.style == "camelCase":
        first, *rest = name.split("_")
        name = first + "".join(word.capitalize() for word in rest)
    elif config.naming.style != "snake_case":
        raise ValueError("naming.style must be snake_case or camelCase.")
    if truncate and len(name) > config.naming.max_event_length:
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

    Merge identical full event names without losing contributing node IDs,
    plus one pageview event per unique screen. Reject truncation collisions.
    """
    events: list[TaxonomyEvent] = []
    events_by_name: dict[str, TaxonomyEvent] = {}
    full_names: dict[str, str] = {}
    screens_seen: set[str] = set()
    global_props = _get_global_properties(config)

    def add_event(event: TaxonomyEvent, full_name: str) -> None:
        name = event.event_name
        if name in events_by_name:
            previous = events_by_name[name]
            if full_names[name] != full_name:
                raise ValueError(
                    f"Event names '{full_names[name]}' (nodes {previous.source_node_ids}) "
                    f"and '{full_name}' (nodes {event.source_node_ids}) truncate to '{name}'. "
                    "Increase naming.max_event_length, change naming.pattern, or rename the controls."
                )
            previous.source_node_ids.extend(
                node for node in event.source_node_ids if node not in previous.source_node_ids
            )
            return
        events_by_name[name] = event
        full_names[name] = full_name
        events.append(event)

    screen_flow_map: dict[str, str] = {}
    for elem in elements:
        if elem.parent_path:
            screen_flow_map[elem.screen_name] = elem.parent_path[0]

    for elem in elements:
        action = config.naming.actions.get(elem.element_type, "clicked")
        element_name = _clean_element_name(elem, config)
        event_name = _build_event_name(elem.screen_name, element_name, action, config)

        full_name = _build_event_name(
            elem.screen_name, element_name, action, config, truncate=False,
        )
        screens_seen.add(elem.screen_name)

        rule_props = _get_matching_properties(event_name, config)

        prop_names_seen: set[str] = set()
        all_props: list[EventProperty] = []
        for p in rule_props + global_props:
            if p.name not in prop_names_seen:
                prop_names_seen.add(p.name)
                all_props.append(p)

        flow = screen_flow_map.get(elem.screen_name, "")
        description = _build_description(elem, action)

        add_event(
            TaxonomyEvent(
                event_name=event_name,
                flow=flow,
                description=description,
                properties=all_props,
                source_node_id=elem.node_id,
            ),
            full_name,
        )

    for screen_name in sorted(screens_seen):
        pv_name = _build_event_name(
            screen_name, "", config.naming.actions.get("screen", "pageview"), config,
        )
        full_name = _build_event_name(
            screen_name, "", config.naming.actions.get("screen", "pageview"),
            config, truncate=False,
        )
        flow = screen_flow_map.get(screen_name, "")
        add_event(
            TaxonomyEvent(
                event_name=pv_name,
                flow=flow,
                description=f"User views {screen_name.replace('_', ' ')} screen",
                properties=list(global_props),
            ),
            full_name,
        )

    return events
