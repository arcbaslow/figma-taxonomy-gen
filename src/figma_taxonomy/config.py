"""Configuration loader: YAML file → typed dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# --- Defaults ---

_DEFAULT_ACTIONS = {
    "button": "clicked",
    "link": "clicked",
    "input": "entered",
    "toggle": "toggled",
    "checkbox": "checked",
    "dropdown": "selected",
    "tab": "viewed",
    "card": "viewed",
    "modal": "opened",
    "form": "submitted",
    "screen": "pageview",
}

_DEFAULT_STRIP_SUFFIXES = ["- Default", "- Light", "- Dark", "- Skeleton"]
_DEFAULT_STRIP_COMMON = ["Component/", "UI/", "Atoms/", "Molecules/", "Organisms/"]
_DEFAULT_EXCLUDE_PAGES = ["Archive", "Drafts", "Components"]

_DEFAULT_GLOBAL_PROPERTIES: list[dict[str, Any]] = [
    {"name": "screen_name", "type": "string", "description": "Screen where event occurred"},
    {"name": "platform", "type": "string", "enum": ["ios", "android", "web"]},
    {"name": "app_version", "type": "string", "description": "Application version"},
]

_DEFAULT_PROPERTY_RULES: list[dict[str, Any]] = [
    {
        "match": "*_clicked",
        "add": [{"name": "element_text", "type": "string", "description": "Visible text of the clicked element"}],
    },
    {
        "match": "*_entered",
        "add": [
            {"name": "field_name", "type": "string", "description": "Name of the input field"},
            {"name": "is_valid", "type": "boolean", "description": "Whether the input passed validation"},
        ],
    },
    {
        "match": "*_fail",
        "add": [{"name": "error_description", "type": "string", "description": "Error description"}],
    },
    {
        "match": "*_payment_success",
        "add": [
            {"name": "insurance_premium", "type": "string", "description": "Insurance premium amount"},
            {"name": "card_type", "type": "string", "description": "Payment card type"},
        ],
    },
]


# --- Config dataclasses ---

@dataclass
class AppConfig:
    type: str = "fintech"
    name: str = "MyApp"


@dataclass
class FigmaConfig:
    exclude_pages: list[str] = field(default_factory=lambda: list(_DEFAULT_EXCLUDE_PAGES))


@dataclass
class ScreenNameConfig:
    strip_prefixes: bool = True
    strip_suffixes: list[str] = field(default_factory=lambda: list(_DEFAULT_STRIP_SUFFIXES))
    max_depth: int = 2


@dataclass
class ElementNameConfig:
    strip_common: list[str] = field(default_factory=lambda: list(_DEFAULT_STRIP_COMMON))
    use_text_content: bool = True
    fallback_to_component_name: bool = True


@dataclass
class NamingConfig:
    style: str = "snake_case"
    pattern: str = "{screen}_{element}_{action}"
    max_event_length: int = 64
    actions: dict[str, str] = field(default_factory=lambda: dict(_DEFAULT_ACTIONS))
    screen_name: ScreenNameConfig = field(default_factory=ScreenNameConfig)
    element_name: ElementNameConfig = field(default_factory=ElementNameConfig)


@dataclass
class OutputConfig:
    formats: list[str] = field(default_factory=lambda: ["excel", "csv", "json", "markdown"])
    directory: str = "./output"


@dataclass
class TaxonomyConfig:
    app: AppConfig = field(default_factory=AppConfig)
    figma: FigmaConfig = field(default_factory=FigmaConfig)
    naming: NamingConfig = field(default_factory=NamingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    global_properties: list[dict[str, Any]] = field(default_factory=lambda: list(_DEFAULT_GLOBAL_PROPERTIES))
    property_rules: list[dict[str, Any]] = field(default_factory=lambda: list(_DEFAULT_PROPERTY_RULES))


def _merge_dict(base: dict, override: dict) -> dict:
    """Shallow merge: override keys replace base keys."""
    merged = dict(base)
    merged.update(override)
    return merged


def load_config(path: Path | None) -> TaxonomyConfig:
    """Load config from a YAML file, falling back to defaults for missing keys."""
    if path is None:
        return TaxonomyConfig()

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    config = TaxonomyConfig()

    if "app" in raw:
        app = raw["app"]
        config.app = AppConfig(
            type=app.get("type", config.app.type),
            name=app.get("name", config.app.name),
        )

    if "figma" in raw:
        fig = raw["figma"]
        config.figma = FigmaConfig(
            exclude_pages=fig.get("exclude_pages", config.figma.exclude_pages),
        )

    if "naming" in raw:
        n = raw["naming"]
        actions = _merge_dict(_DEFAULT_ACTIONS, n.get("actions", {}))

        sn_raw = n.get("screen_name", {})
        screen_name = ScreenNameConfig(
            strip_prefixes=sn_raw.get("strip_prefixes", True),
            strip_suffixes=sn_raw.get("strip_suffixes", list(_DEFAULT_STRIP_SUFFIXES)),
            max_depth=sn_raw.get("max_depth", 2),
        )

        en_raw = n.get("element_name", {})
        element_name = ElementNameConfig(
            strip_common=en_raw.get("strip_common", list(_DEFAULT_STRIP_COMMON)),
            use_text_content=en_raw.get("use_text_content", True),
            fallback_to_component_name=en_raw.get("fallback_to_component_name", True),
        )

        config.naming = NamingConfig(
            style=n.get("style", config.naming.style),
            pattern=n.get("pattern", config.naming.pattern),
            max_event_length=n.get("max_event_length", config.naming.max_event_length),
            actions=actions,
            screen_name=screen_name,
            element_name=element_name,
        )

    if "output" in raw:
        o = raw["output"]
        config.output = OutputConfig(
            formats=o.get("formats", config.output.formats),
            directory=o.get("directory", config.output.directory),
        )

    if "global_properties" in raw:
        config.global_properties = raw["global_properties"]

    if "property_rules" in raw:
        config.property_rules = raw["property_rules"]

    return config
