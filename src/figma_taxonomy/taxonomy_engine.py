"""Naming convention engine: ScreenElements → TaxonomyEvents."""

from __future__ import annotations

import fnmatch
import re

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import EventProperty, Screen, ScreenElement, TaxonomyEvent


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
    page: str = "",
) -> str:
    if config.naming.max_event_length <= 0:
        raise ValueError("naming.max_event_length must be a positive integer.")
    try:
        name = config.naming.pattern.format(
            page=_to_snake_case(page), screen=screen, element=element_name, action=action,
        )
    except (KeyError, ValueError, IndexError, AttributeError) as exc:
        raise ValueError(
            "naming.pattern must use {page}, {screen}, {element} and/or {action} placeholders."
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
    elements: list[ScreenElement], config: TaxonomyConfig,
    *, screens: list[Screen] | None = None,
) -> list[TaxonomyEvent]:
    """Generate taxonomy events from extracted screen elements.

    Merge identical full event names without losing contributing node IDs,
    plus pageviews with frame provenance. Pass the screen inventory to include
    empty screens. Reject truncation collisions and events shared across pages.
    """
    events: list[TaxonomyEvent] = []
    events_by_name: dict[str, TaxonomyEvent] = {}
    full_names: dict[str, str] = {}
    event_pages: dict[str, tuple[str, str]] = {}
    event_kinds: dict[str, str] = {}
    global_props = _get_global_properties(config)

    def add_event(
        event: TaxonomyEvent, full_name: str, page_id: str, kind: str,
    ) -> None:
        name = event.event_name
        page_key = ("id", page_id) if page_id else ("name", event.flow)
        if name in events_by_name:
            previous = events_by_name[name]
            if full_names[name] != full_name:
                raise ValueError(
                    f"Event names '{full_names[name]}' (nodes {previous.source_node_ids}) "
                    f"and '{full_name}' (nodes {event.source_node_ids}) truncate to '{name}'. "
                    "Increase naming.max_event_length, change naming.pattern, or rename the controls."
                )
            if event_pages[name] != page_key:
                raise ValueError(
                    f"Event '{name}' belongs to different Figma pages: "
                    f"'{previous.flow}' ({event_pages[name][1]}) and '{event.flow}' ({page_key[1]}). "
                    "Add {page} to naming.pattern or rename the screens. "
                    "If page names normalize identically, rename the pages too."
                )
            if event_kinds[name] != kind:
                raise ValueError(
                    f"Event '{name}' combines a control and a pageview. "
                    "Include {action} in naming.pattern and use distinct control and screen actions."
                )
            previous.source_node_ids.extend(
                node for node in event.source_node_ids if node not in previous.source_node_ids
            )
            if not previous.source_node_id and previous.source_node_ids:
                previous.source_node_id = previous.source_node_ids[0]
            return
        events_by_name[name] = event
        full_names[name] = full_name
        event_pages[name] = page_key
        event_kinds[name] = kind
        events.append(event)

    screen_inventory = list(screens or [])
    screen_inventory.extend(
        Screen(
            node_id=elem.screen_node_id, screen_name=elem.screen_name,
            page_name=elem.parent_path[0] if elem.parent_path else "", page_id=elem.page_id,
        )
        for elem in elements
    )

    for elem in elements:
        action = config.naming.actions.get(elem.element_type, "clicked")
        element_name = _clean_element_name(elem, config)
        flow = elem.parent_path[0] if elem.parent_path else ""
        event_name = _build_event_name(elem.screen_name, element_name, action, config, page=flow)

        full_name = _build_event_name(
            elem.screen_name, element_name, action, config, truncate=False, page=flow,
        )

        rule_props = _get_matching_properties(event_name, config)

        prop_names_seen: set[str] = set()
        all_props: list[EventProperty] = []
        for p in rule_props + global_props:
            if p.name not in prop_names_seen:
                prop_names_seen.add(p.name)
                all_props.append(p)

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
            elem.page_id,
            "control",
        )

    unique_screens = {
        (s.page_id, s.page_name, s.screen_name, s.node_id): s for s in screen_inventory
    }
    for screen in sorted(unique_screens.values(), key=lambda s: (s.screen_name, s.page_name, s.page_id)):
        pv_name = _build_event_name(
            screen.screen_name, "", config.naming.actions.get("screen", "pageview"),
            config, page=screen.page_name,
        )
        full_name = _build_event_name(
            screen.screen_name, "", config.naming.actions.get("screen", "pageview"),
            config, truncate=False, page=screen.page_name,
        )
        add_event(
            TaxonomyEvent(
                event_name=pv_name,
                flow=screen.page_name,
                description=f"User views {screen.screen_name.replace('_', ' ')} screen",
                properties=list(global_props),
                source_node_id=screen.node_id,
            ),
            full_name,
            screen.page_id,
            "pageview",
        )

    return events
