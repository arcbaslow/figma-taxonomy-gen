"""Extract interactive UI elements from a Figma file tree."""

from __future__ import annotations

import fnmatch
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
    return bool(interactions) or bool(node.get("transitionNodeID"))


def _classify_node(node: dict, config: TaxonomyConfig) -> tuple[str | None, str, int | None]:
    """One decision function for extraction and explanation, with stable reason codes."""
    if not config.detection.include_hidden and node.get("visible") is False:
        return None, "hidden", None
    name = node.get("name", "")
    for index, rule in enumerate(config.detection.overrides):
        if ((rule.node_id and rule.node_id == node.get("id"))
                or (rule.match and fnmatch.fnmatchcase(name.casefold(), rule.match.casefold()))):
            if rule.action == "exclude":
                return None, "override_exclude", index
            return rule.type, "override_include", index
    if _is_excluded(name):
        return None, "excluded_name", None
    kind = _classify_element(name)
    if _has_interactions(node):
        reason = "prototype_interaction" if node.get("interactions") else "legacy_transition"
        return kind or "interactive", reason, None
    if kind is not None and node.get("type") in _COMPONENT_TYPES:
        return kind, "component_name", None
    return None, "not_interactive", None


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


def _extract_text_content(node: dict, config: TaxonomyConfig | None = None) -> str | None:
    if node.get("visible") is False:
        return None
    if node.get("characters"):
        return node["characters"]
    children = [child for child in node.get("children", [])
                if child.get("visible") is not False and not _is_excluded(child.get("name", ""))]
    for child in children:
        if child.get("type") == "TEXT" and child.get("name", "").lower() in (
            "label",
            "text",
            "title",
            "value",
        ):
            if child.get("characters"):
                return child["characters"]
    for child in children:
        if child.get("type") == "TEXT" and child.get("characters"):
            if not _is_excluded(child.get("name", "")):
                return child["characters"]
    for child in children:
        # A nested control owns its own text, not its enclosing card/form.
        if config is not None:
            child_kind, child_reason, _ = _classify_node(child, config)
            if child_kind is not None or child_reason in {"hidden", "override_exclude", "excluded_name"}:
                continue
        if _has_interactions(child) or (
            child.get("type") in _COMPONENT_TYPES and _classify_element(child.get("name", ""))
        ):
            continue
        if text := _extract_text_content(child, config):
            return text
    return None


def _screen_frames(container: dict, include_hidden: bool = True) -> Iterator[dict]:
    """Sections organize screens; frames contain screen layout, so stop there."""
    for child in container.get("children", []):
        if not include_hidden and child.get("visible") is False:
            continue
        if child.get("type") == "FRAME":
            yield child
        elif child.get("type") == "SECTION":
            yield from _screen_frames(child, include_hidden)


def _variants(node: dict) -> list[str]:
    properties = node.get("componentProperties", {})
    if not isinstance(properties, dict):
        return []
    return [f"{name}={prop['value']}" for name, prop in sorted(properties.items())
            if isinstance(prop, dict) and prop.get("type") == "VARIANT"
            and isinstance(prop.get("value"), str)]


def _walk_node(
    node: dict,
    screen_name: str,
    page_name: str,
    parent_path: list[str],
    config: TaxonomyConfig,
) -> list[ScreenElement]:
    elements: list[ScreenElement] = []
    name = node.get("name", "")
    element_type, reason, _ = _classify_node(node, config)
    if reason in {"hidden", "override_exclude", "excluded_name"}:
        return elements

    has_interaction = _has_interactions(node)
    if element_type is not None:
        text_content = _extract_text_content(node, config)

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
                variants=_variants(node),
                parent_path=list(parent_path),
            )
        )
        if not config.detection.traverse_interactive_children:
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
        if not config.detection.include_hidden and page.get("visible") is False:
            continue
        for frame in _screen_frames(page, config.detection.include_hidden):
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
