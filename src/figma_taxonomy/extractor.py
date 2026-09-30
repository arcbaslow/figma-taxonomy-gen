"""Extract interactive UI elements from a Figma file tree."""

from __future__ import annotations

import re
from collections.abc import Iterator

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import Screen, ScreenElement

INTERACTIVE_PATTERNS = [
    (re.compile(p, re.IGNORECASE), element_type)
    for p, element_type in [
        (r"button|btn|cta", "button"),
        (r"link|anchor", "link"),
        (r"input|field|text.?field|search.?bar", "input"),
        (r"toggle|switch", "toggle"),
        (r"checkbox|check.?box", "checkbox"),
        (r"radio", "radio"),
        (r"dropdown|select|picker", "dropdown"),
        (r"tab|tab.?bar", "tab"),
        (r"card", "card"),
        (r"modal|dialog|sheet", "modal"),
        (r"nav.?bar|bottom.?nav", "nav"),
        (r"carousel|slider", "carousel"),
        (r"chip|tag|badge", "chip"),
        (r"form", "form"),
    ]
]

EXCLUDE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"^icon",
        r"divider",
        r"separator",
        r"placeholder",
        r"hint",
        r"loader",
        r"spinner",
        r"logo",
    ]
]

_COMPONENT_TYPES = {"COMPONENT", "COMPONENT_SET", "INSTANCE"}

_PREFIX_RE = re.compile(r"^\d+\s*[-–.]\s*")


def _is_excluded(name: str) -> bool:
    return any(pat.search(name) for pat in EXCLUDE_PATTERNS)


def _classify_element(name: str) -> str | None:
    for pattern, element_type in INTERACTIVE_PATTERNS:
        if pattern.search(name):
            return element_type
    return None


def _has_interactions(node: dict) -> bool:
    interactions = node.get("interactions")
    return bool(interactions and len(interactions) > 0)


def _clean_screen_name(raw: str, config: TaxonomyConfig) -> str:
    name = raw
    sn_config = config.naming.screen_name

    if sn_config.strip_prefixes:
        name = _PREFIX_RE.sub("", name)

    for suffix in sn_config.strip_suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]

    name = name.strip().strip("-").strip()
    name = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return name


def _extract_text_content(node: dict) -> str | None:
    if node.get("characters"):
        return node["characters"]
    for child in node.get("children", []):
        if child.get("type") == "TEXT" and child.get("name", "").lower() in (
            "label",
            "text",
            "title",
            "value",
        ):
            if child.get("characters"):
                return child["characters"]
    for child in node.get("children", []):
        if child.get("type") == "TEXT" and child.get("characters"):
            if not _is_excluded(child.get("name", "")):
                return child["characters"]
    return None


def _screen_frames(container: dict) -> Iterator[dict]:
    """Sections organize screens; frames contain screen layout, so stop there."""
    for child in container.get("children", []):
        if child.get("type") == "FRAME":
            yield child
        elif child.get("type") == "SECTION":
            yield from _screen_frames(child)


def _walk_node(
    node: dict,
    screen_name: str,
    page_name: str,
    parent_path: list[str],
    config: TaxonomyConfig,
) -> list[ScreenElement]:
    elements: list[ScreenElement] = []
    name = node.get("name", "")
    node_type = node.get("type", "")

    if _is_excluded(name):
        return elements

    element_type = _classify_element(name)
    has_interaction = _has_interactions(node)

    is_interactive_component = element_type is not None and node_type in _COMPONENT_TYPES
    is_interactive_frame = has_interaction

    if is_interactive_component or is_interactive_frame:
        text_content = _extract_text_content(node)

        clean_name = name
        for prefix in config.naming.element_name.strip_common:
            if clean_name.startswith(prefix):
                clean_name = clean_name[len(prefix):]
                break

        final_type = element_type or "interactive"

        elements.append(
            ScreenElement(
                node_id=node["id"],
                screen_name=screen_name,
                element_name=clean_name,
                element_type=final_type,
                text_content=text_content,
                has_interaction=has_interaction,
                variants=[],
                parent_path=list(parent_path),
            )
        )
        return elements

    for child in node.get("children", []):
        elements.extend(
            _walk_node(child, screen_name, page_name, parent_path, config)
        )

    return elements


def _page_frames(figma_file: dict, config: TaxonomyConfig) -> Iterator[tuple[dict, dict]]:
    """Apply the same page scope to controls and screen inventory."""
    document = figma_file.get("document", figma_file)
    for page in document.get("children", []):
        if page.get("type") not in ("CANVAS", "PAGE"):
            continue
        if page.get("name", "") in config.figma.exclude_pages:
            continue
        for frame in _screen_frames(page):
            yield page, frame


def extract_screens(figma_file: dict, config: TaxonomyConfig) -> list[Screen]:
    """Inventory every in-scope screen frame, including empty variants/screens."""
    return [
        Screen(
            node_id=frame.get("id", ""),
            screen_name=_clean_screen_name(frame["name"], config),
            page_name=page.get("name", ""),
            page_id=page.get("id", ""),
        )
        for page, frame in _page_frames(figma_file, config)
    ]


def extract_elements(figma_file: dict, config: TaxonomyConfig) -> list[ScreenElement]:
    """Extract interactive controls, retaining their page and screen frame IDs."""
    all_elements: list[ScreenElement] = []
    for page, frame in _page_frames(figma_file, config):
        page_name = page.get("name", "")
        screen_name = _clean_screen_name(frame["name"], config)
        elements = _walk_node(frame, screen_name, page_name, [page_name, frame["name"]], config)
        for element in elements:
            element.page_id = page.get("id", "")
            element.screen_node_id = frame.get("id", "")
        all_elements.extend(elements)
    return all_elements
