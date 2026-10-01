"""Configuration loader: YAML file → typed dataclasses."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from string import Formatter
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
class AIConfig:
    enabled: bool = False
    model: str = "claude-haiku-4-5-20251001"
    max_tokens: int = 2048
    batch_size: int = 20
    max_prompt_chars: int = 12000


@dataclass
class DetectionOverride:
    match: str = ""
    node_id: str = ""
    action: str = "include"
    type: str = "interactive"


@dataclass
class DetectionConfig:
    include_hidden: bool = True
    traverse_interactive_children: bool = False
    overrides: list[DetectionOverride] = field(default_factory=list)


@dataclass
class TaxonomyConfig:
    app: AppConfig = field(default_factory=AppConfig)
    figma: FigmaConfig = field(default_factory=FigmaConfig)
    naming: NamingConfig = field(default_factory=NamingConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    global_properties: list[dict[str, Any]] = field(default_factory=lambda: deepcopy(_DEFAULT_GLOBAL_PROPERTIES))
    property_rules: list[dict[str, Any]] = field(default_factory=lambda: deepcopy(_DEFAULT_PROPERTY_RULES))


def _merge_dict(base: dict, override: dict) -> dict:
    """Shallow merge: override keys replace base keys."""
    merged = dict(base)
    merged.update(override)
    return merged


def _validate_properties(properties: Any, location: str) -> None:
    if not isinstance(properties, list):
        raise ValueError(f"{location} must be a list of property definitions.")
    names: set[str] = set()
    for prop in properties:
        if not isinstance(prop, dict) or set(prop) - {"name", "type", "description", "enum"}:
            raise ValueError(f"{location} entries accept name, type, description and enum only.")
        name = prop.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError(f"{location} requires unique non-empty property names.")
        names.add(name)
        for key in ("type", "description"):
            if key in prop and not isinstance(prop[key], str):
                raise ValueError(f"{location}.{name}.{key} must be a string.")
        if "enum" in prop and (not isinstance(prop["enum"], list) or not prop["enum"]):
            raise ValueError(f"{location}.{name}.enum must be a non-empty list.")


def _validate_shape(value: Any, default: Any, location: str = "config") -> None:
    if location == "config.detection.overrides":
        if not isinstance(value, list):
            raise ValueError(f"{location} must be a list of override mappings.")
        for rule in value:
            if not isinstance(rule, dict) or set(rule) - {"match", "node_id", "action", "type"}:
                raise ValueError(f"{location} accepts match or node_id, action and type only.")
            selectors = set(rule) & {"match", "node_id"}
            if len(selectors) != 1 or any(not isinstance(v, str) or not v.strip() for v in rule.values()):
                raise ValueError(f"{location} requires one non-empty match or node_id selector and string values.")
            if rule.get("action", "include") not in {"include", "exclude"}:
                raise ValueError(f"{location}.action must be include or exclude.")
    elif location == "config.global_properties":
        _validate_properties(value, location)
    elif location == "config.property_rules":
        if not isinstance(value, list):
            raise ValueError(f"{location} must be a list.")
        for rule in value:
            if not isinstance(rule, dict) or set(rule) != {"match", "add"}:
                raise ValueError(f"{location} entries require match and add.")
            if not isinstance(rule["match"], str) or not rule["match"]:
                raise ValueError(f"{location}.match must be a non-empty glob pattern.")
            _validate_properties(rule["add"], f"{location}.add")
    elif location == "config.naming.actions":
        if not isinstance(value, dict) or any(
            not isinstance(k, str) or not k or not isinstance(v, str) or not v
            for k, v in value.items()
        ):
            raise ValueError(f"{location} must map component types to non-empty action strings.")
    elif isinstance(default, dict):
        if not isinstance(value, dict):
            raise ValueError(f"{location} must be a mapping.")
        for key, item in value.items():
            if key not in default:
                raise ValueError(f"Unknown setting {location}.{key}.")
            _validate_shape(item, default[key], f"{location}.{key}")
    elif isinstance(default, list):
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{location} must be a list of strings.")
    elif type(value) is not type(default):
        raise ValueError(f"{location} must be {type(default).__name__}.")


def _validate_config(config: TaxonomyConfig) -> None:
    if config.naming.style not in {"snake_case", "camelCase"}:
        raise ValueError("naming.style must be snake_case or camelCase.")
    if config.naming.max_event_length < 1:
        raise ValueError("naming.max_event_length must be positive.")
    if config.naming.screen_name.max_depth != 2:
        raise ValueError("naming.screen_name.max_depth is reserved; only the legacy value 2 is supported. Screens are top-level frames inside pages/sections.")
    try:
        parts = list(Formatter().parse(config.naming.pattern))
        if not config.naming.pattern or any(
            name is not None and (name not in {"page", "screen", "element", "action"} or spec or conversion)
            for _, name, spec, conversion in parts
        ):
            raise ValueError()
    except ValueError as exc:
        raise ValueError("naming.pattern supports plain {page}, {screen}, {element}, {action} placeholders only.") from exc
    supported = {"excel", "csv", "json", "markdown", "amplitude-csv"}
    if not config.output.formats or set(config.output.formats) - supported:
        raise ValueError("output.formats must be a non-empty list of supported formats: " + ", ".join(sorted(supported)))
    if not config.output.directory.strip():
        raise ValueError("output.directory must be non-empty.")
    if config.ai.max_tokens < 1 or not config.ai.model.strip():
        raise ValueError("ai.max_tokens must be positive and ai.model must be non-empty.")
    if config.ai.batch_size < 1 or config.ai.max_prompt_chars < 1:
        raise ValueError("ai.batch_size and ai.max_prompt_chars must be positive.")


def load_config(path: Path | None) -> TaxonomyConfig:
    """Load config from a YAML file, falling back to defaults for missing keys."""
    if path is None:
        return TaxonomyConfig()

    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}" if mark is not None else ""
        raise ValueError(f"Invalid YAML in {path}{location}; check indentation and syntax.") from exc
    if raw is None:
        raw = {}
    _validate_shape(raw, asdict(TaxonomyConfig()))

    config = TaxonomyConfig()

    if "detection" in raw:
        detection = raw["detection"]
        config.detection = DetectionConfig(
            include_hidden=detection.get("include_hidden", True),
            traverse_interactive_children=detection.get("traverse_interactive_children", False),
            overrides=[DetectionOverride(**rule) for rule in detection.get("overrides", [])],
        )

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

    if "ai" in raw:
        a = raw["ai"]
        config.ai = AIConfig(
            enabled=a.get("enabled", config.ai.enabled),
            model=a.get("model", config.ai.model),
            max_tokens=a.get("max_tokens", config.ai.max_tokens),
            batch_size=a.get("batch_size", config.ai.batch_size),
            max_prompt_chars=a.get("max_prompt_chars", config.ai.max_prompt_chars),
        )

    if "global_properties" in raw:
        config.global_properties = raw["global_properties"]

    if "property_rules" in raw:
        config.property_rules = raw["property_rules"]

    _validate_config(config)
    return config
