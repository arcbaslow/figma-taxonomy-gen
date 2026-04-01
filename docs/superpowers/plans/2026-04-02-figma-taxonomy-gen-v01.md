# figma-taxonomy-gen v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that extracts interactive UI elements from Figma designs and generates an Amplitude event taxonomy in Excel, CSV, JSON, and Markdown formats.

**Architecture:** Modular Python library with four pipeline stages: Figma API client → extractor (node walker + interactive element filter) → taxonomy engine (naming conventions + property rules) → output formatters. Click-based CLI orchestrates the pipeline. Config via YAML dataclasses.

**Tech Stack:** Python 3.11+, uv, click, httpx, openpyxl, PyYAML, pytest

---

## File Structure

```
figma-taxonomy-gen/
├── pyproject.toml                          # Package config, dependencies, CLI entrypoint
├── taxonomy.config.yaml                    # Default naming convention config
├── LICENSE                                 # MIT
├── README.md                               # User-facing docs
├── .gitignore                              # Python + cache ignores
│
├── src/figma_taxonomy/
│   ├── __init__.py                         # Package version
│   ├── models.py                           # Dataclasses: ScreenElement, TaxonomyEvent, EventProperty, TaxonomyConfig
│   ├── config.py                           # YAML → TaxonomyConfig loader
│   ├── figma_client.py                     # Figma REST API wrapper + file version caching
│   ├── extractor.py                        # Node tree walker, interactive element filter, screen map builder
│   ├── taxonomy_engine.py                  # Naming convention engine, event generator, property rules
│   ├── cli.py                              # Click CLI: extract command
│   └── output/
│       ├── __init__.py                     # Formatter registry
│       ├── excel.py                        # .xlsx output matching template structure
│       ├── amplitude_csv.py                # Amplitude Data import CSV
│       ├── json_schema.py                  # JSON Schema output
│       └── markdown.py                     # Human-readable tracking plan
│
├── tests/
│   ├── conftest.py                         # Shared fixtures
│   ├── fixtures/
│   │   └── banking_app.json                # Realistic Figma API response
│   ├── test_config.py                      # Config loading tests
│   ├── test_extractor.py                   # Extraction + filtering tests
│   ├── test_taxonomy_engine.py             # Naming + property rule tests
│   └── test_output.py                      # Output format tests
│
└── examples/
    └── banking-app/                        # Generated example outputs
```

---

### Task 0: Repository setup + project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `src/figma_taxonomy/__init__.py`
- Create: `src/figma_taxonomy/output/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Initialize git repo and create GitHub remote**

```bash
cd "/c/Program Data/Web/figma-amplitude-taxanomy"
git init
gh repo create figma-taxonomy-gen --public --description "CLI tool that extracts interactive UI elements from Figma designs and generates Amplitude event taxonomies" --source . --push
```

- [ ] **Step 2: Create .gitignore**

Create `.gitignore`:
```
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
build/
.eggs/
*.egg
.venv/
venv/
.env
.figma-taxonomy-cache/
output/
*.xlsx
!taxonomy.config.yaml
.pytest_cache/
.mypy_cache/
```

- [ ] **Step 3: Create pyproject.toml**

Create `pyproject.toml`:
```toml
[project]
name = "figma-taxonomy-gen"
version = "0.1.0"
description = "Extract interactive UI elements from Figma designs and generate Amplitude event taxonomies"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1",
    "httpx>=0.27",
    "pyyaml>=6.0",
    "openpyxl>=3.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[project.scripts]
figma-taxonomy = "figma_taxonomy.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/figma_taxonomy"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 4: Create LICENSE**

Create `LICENSE` with MIT license text, copyright 2026 arcbaslow.

- [ ] **Step 5: Create package init files**

Create `src/figma_taxonomy/__init__.py`:
```python
"""Extract interactive UI elements from Figma designs and generate Amplitude event taxonomies."""

__version__ = "0.1.0"
```

Create `src/figma_taxonomy/output/__init__.py`:
```python
"""Output formatters for taxonomy data."""
```

Create `tests/__init__.py`:
```python
```

Create `tests/conftest.py`:
```python
import json
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def banking_app_fixture():
    """Load the banking app Figma API response fixture."""
    with open(FIXTURES_DIR / "banking_app.json") as f:
        return json.load(f)
```

- [ ] **Step 6: Install dependencies**

```bash
uv sync
uv run pytest --co  # verify pytest discovers test directory (0 tests collected is fine)
```

- [ ] **Step 7: Commit**

```bash
git add .gitignore pyproject.toml LICENSE src/ tests/
git commit -m "chore: initial project scaffolding with pyproject.toml and package structure"
```

---

### Task 1: Data models

**Files:**
- Create: `src/figma_taxonomy/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_models.py`:
```python
from figma_taxonomy.models import ScreenElement, TaxonomyEvent, EventProperty


def test_screen_element_creation():
    elem = ScreenElement(
        node_id="1:234",
        screen_name="onboarding_welcome",
        element_name="get_started",
        element_type="button",
        text_content="Get Started",
        has_interaction=True,
        variants=[],
        parent_path=["Onboarding", "01 - Welcome"],
    )
    assert elem.node_id == "1:234"
    assert elem.element_type == "button"
    assert elem.text_content == "Get Started"


def test_event_property_creation():
    prop = EventProperty(
        name="error_description",
        type="string",
        description="Description of the error",
        enum_values=None,
    )
    assert prop.name == "error_description"
    assert prop.enum_values is None


def test_event_property_with_enum():
    prop = EventProperty(
        name="platform",
        type="string",
        description="User platform",
        enum_values=["ios", "android", "web"],
    )
    assert prop.enum_values == ["ios", "android", "web"]


def test_taxonomy_event_creation():
    props = [
        EventProperty(
            name="screen_name",
            type="string",
            description="Screen where event occurred",
            enum_values=None,
        )
    ]
    event = TaxonomyEvent(
        event_name="login_pageview",
        flow="Authentication",
        description="User views login screen",
        properties=props,
        source_node_id="2:100",
    )
    assert event.event_name == "login_pageview"
    assert event.flow == "Authentication"
    assert len(event.properties) == 1
    assert event.source_node_id == "2:100"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'figma_taxonomy.models'`

- [ ] **Step 3: Write minimal implementation**

Create `src/figma_taxonomy/models.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/figma_taxonomy/models.py tests/test_models.py
git commit -m "feat: add core data models (ScreenElement, TaxonomyEvent, EventProperty)"
```

---

### Task 2: Configuration loader

**Files:**
- Create: `src/figma_taxonomy/config.py`
- Create: `taxonomy.config.yaml`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_config.py`:
```python
import textwrap
from pathlib import Path

from figma_taxonomy.config import TaxonomyConfig, load_config


def test_load_default_config():
    """Loading config without a file returns sensible defaults."""
    config = load_config(None)
    assert config.naming.style == "snake_case"
    assert config.naming.actions["button"] == "clicked"
    assert config.naming.actions["input"] == "entered"
    assert config.naming.actions["screen"] == "pageview"
    assert config.naming.max_event_length == 64


def test_load_config_from_yaml(tmp_path):
    """Loading a YAML file overrides defaults."""
    yaml_content = textwrap.dedent("""\
        app:
          type: ecommerce
          name: "TestShop"
        naming:
          style: camelCase
          actions:
            button: "tapped"
    """)
    config_file = tmp_path / "test.yaml"
    config_file.write_text(yaml_content)

    config = load_config(config_file)
    assert config.app.name == "TestShop"
    assert config.app.type == "ecommerce"
    assert config.naming.style == "camelCase"
    assert config.naming.actions["button"] == "tapped"
    # Non-overridden defaults still present
    assert config.naming.actions["input"] == "entered"


def test_config_screen_name_settings():
    config = load_config(None)
    assert config.naming.screen_name.strip_prefixes is True
    assert "- Default" in config.naming.screen_name.strip_suffixes


def test_config_global_properties():
    config = load_config(None)
    names = [p["name"] for p in config.global_properties]
    assert "screen_name" in names
    assert "platform" in names


def test_config_property_rules():
    config = load_config(None)
    fail_rule = next(r for r in config.property_rules if r["match"] == "*_fail")
    prop_names = [p["name"] for p in fail_rule["add"]]
    assert "error_description" in prop_names


def test_config_output_defaults():
    config = load_config(None)
    assert "excel" in config.output.formats
    assert "csv" in config.output.formats
    assert "json" in config.output.formats
    assert "markdown" in config.output.formats


def test_config_exclude_pages():
    config = load_config(None)
    assert "Archive" in config.figma.exclude_pages
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create the default config YAML**

Create `taxonomy.config.yaml`:
```yaml
app:
  type: fintech
  name: "MyApp"

figma:
  exclude_pages: ["Archive", "Drafts", "Components"]

naming:
  style: snake_case
  pattern: "{screen}_{element}_{action}"
  max_event_length: 64

  actions:
    button: "clicked"
    link: "clicked"
    input: "entered"
    toggle: "toggled"
    checkbox: "checked"
    dropdown: "selected"
    tab: "viewed"
    card: "viewed"
    modal: "opened"
    form: "submitted"
    screen: "pageview"

  screen_name:
    strip_prefixes: true
    strip_suffixes: ["- Default", "- Light", "- Dark", "- Skeleton"]
    max_depth: 2

  element_name:
    strip_common: ["Component/", "UI/", "Atoms/", "Molecules/", "Organisms/"]
    use_text_content: true
    fallback_to_component_name: true

output:
  formats: ["excel", "csv", "json", "markdown"]
  directory: "./output"

global_properties:
  - name: "screen_name"
    type: "string"
    description: "Screen where event occurred"
  - name: "platform"
    type: "string"
    enum: ["ios", "android", "web"]
  - name: "app_version"
    type: "string"
    description: "Application version"

property_rules:
  - match: "*_clicked"
    add:
      - name: "element_text"
        type: "string"
        description: "Visible text of the clicked element"
  - match: "*_entered"
    add:
      - name: "field_name"
        type: "string"
        description: "Name of the input field"
      - name: "is_valid"
        type: "boolean"
        description: "Whether the input passed validation"
  - match: "*_fail"
    add:
      - name: "error_description"
        type: "string"
        description: "Error description"
  - match: "*_payment_success"
    add:
      - name: "insurance_premium"
        type: "string"
        description: "Insurance premium amount"
      - name: "card_type"
        type: "string"
        description: "Payment card type"
```

- [ ] **Step 4: Write the config loader implementation**

Create `src/figma_taxonomy/config.py`:
```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add src/figma_taxonomy/config.py taxonomy.config.yaml tests/test_config.py
git commit -m "feat: add config loader with YAML support and sensible defaults"
```

---

### Task 3: Test fixtures

**Files:**
- Create: `tests/fixtures/banking_app.json`

- [ ] **Step 1: Create the banking app Figma API response fixture**

This fixture simulates a real Figma `GET /v1/files/:key` response. It models a small banking app with 3 pages (Login, Home, Payments), each containing frames with interactive components.

Create `tests/fixtures/banking_app.json`:
```json
{
  "name": "Banking App",
  "lastModified": "2026-03-15T10:30:00Z",
  "version": "123456",
  "document": {
    "id": "0:0",
    "name": "Document",
    "type": "DOCUMENT",
    "children": [
      {
        "id": "1:0",
        "name": "Login",
        "type": "CANVAS",
        "children": [
          {
            "id": "1:1",
            "name": "01 - Login Screen",
            "type": "FRAME",
            "children": [
              {
                "id": "1:10",
                "name": "Input/Email",
                "type": "INSTANCE",
                "componentId": "C:1",
                "characters": null,
                "children": [
                  {
                    "id": "1:11",
                    "name": "Placeholder",
                    "type": "TEXT",
                    "characters": "Enter email"
                  }
                ]
              },
              {
                "id": "1:12",
                "name": "Input/Password",
                "type": "INSTANCE",
                "componentId": "C:2",
                "characters": null,
                "children": [
                  {
                    "id": "1:13",
                    "name": "Placeholder",
                    "type": "TEXT",
                    "characters": "Enter password"
                  }
                ]
              },
              {
                "id": "1:14",
                "name": "Button/Primary",
                "type": "INSTANCE",
                "componentId": "C:3",
                "children": [
                  {
                    "id": "1:15",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Log In"
                  }
                ]
              },
              {
                "id": "1:16",
                "name": "Link/ForgotPassword",
                "type": "INSTANCE",
                "componentId": "C:4",
                "children": [
                  {
                    "id": "1:17",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Forgot password?"
                  }
                ]
              },
              {
                "id": "1:18",
                "name": "Divider",
                "type": "RECTANGLE"
              },
              {
                "id": "1:19",
                "name": "Logo",
                "type": "INSTANCE",
                "componentId": "C:99"
              },
              {
                "id": "1:20",
                "name": "Toggle/RememberMe",
                "type": "INSTANCE",
                "componentId": "C:5",
                "children": [
                  {
                    "id": "1:21",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Remember me"
                  }
                ]
              }
            ]
          },
          {
            "id": "1:2",
            "name": "01 - Login Screen - Dark",
            "type": "FRAME",
            "children": [
              {
                "id": "1:30",
                "name": "Button/Primary",
                "type": "INSTANCE",
                "componentId": "C:3",
                "children": [
                  {
                    "id": "1:31",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Log In"
                  }
                ]
              }
            ]
          }
        ]
      },
      {
        "id": "2:0",
        "name": "Home",
        "type": "CANVAS",
        "children": [
          {
            "id": "2:1",
            "name": "Home - Default",
            "type": "FRAME",
            "children": [
              {
                "id": "2:10",
                "name": "Card/AccountBalance",
                "type": "INSTANCE",
                "componentId": "C:10",
                "children": [
                  {
                    "id": "2:11",
                    "name": "Title",
                    "type": "TEXT",
                    "characters": "Account Balance"
                  }
                ]
              },
              {
                "id": "2:12",
                "name": "Button/Transfer",
                "type": "INSTANCE",
                "componentId": "C:11",
                "children": [
                  {
                    "id": "2:13",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Transfer"
                  }
                ]
              },
              {
                "id": "2:14",
                "name": "Button/Pay",
                "type": "INSTANCE",
                "componentId": "C:12",
                "children": [
                  {
                    "id": "2:15",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Pay Bills"
                  }
                ]
              },
              {
                "id": "2:16",
                "name": "Tab/Accounts",
                "type": "INSTANCE",
                "componentId": "C:13",
                "children": [
                  {
                    "id": "2:17",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Accounts"
                  }
                ]
              },
              {
                "id": "2:18",
                "name": "Tab/Cards",
                "type": "INSTANCE",
                "componentId": "C:14",
                "children": [
                  {
                    "id": "2:19",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Cards"
                  }
                ]
              },
              {
                "id": "2:20",
                "name": "BottomNav",
                "type": "INSTANCE",
                "componentId": "C:15"
              },
              {
                "id": "2:22",
                "name": "Loader",
                "type": "INSTANCE",
                "componentId": "C:50"
              }
            ]
          }
        ]
      },
      {
        "id": "3:0",
        "name": "Payments",
        "type": "CANVAS",
        "children": [
          {
            "id": "3:1",
            "name": "Payment Form",
            "type": "FRAME",
            "children": [
              {
                "id": "3:10",
                "name": "Input/Amount",
                "type": "INSTANCE",
                "componentId": "C:20",
                "children": [
                  {
                    "id": "3:11",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Amount"
                  }
                ]
              },
              {
                "id": "3:12",
                "name": "Dropdown/AccountSelect",
                "type": "INSTANCE",
                "componentId": "C:21",
                "children": [
                  {
                    "id": "3:13",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Select Account"
                  }
                ]
              },
              {
                "id": "3:14",
                "name": "Checkbox/SaveRecipient",
                "type": "INSTANCE",
                "componentId": "C:22",
                "children": [
                  {
                    "id": "3:15",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Save recipient"
                  }
                ]
              },
              {
                "id": "3:16",
                "name": "Button/Submit",
                "type": "INSTANCE",
                "componentId": "C:23",
                "children": [
                  {
                    "id": "3:17",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Send Payment"
                  }
                ]
              },
              {
                "id": "3:18",
                "name": "InteractiveFrame",
                "type": "FRAME",
                "interactions": [
                  {"trigger": {"type": "ON_CLICK"}, "action": {"type": "NAVIGATE", "destinationId": "4:0"}}
                ],
                "children": []
              }
            ]
          },
          {
            "id": "3:2",
            "name": "Payment Success",
            "type": "FRAME",
            "children": [
              {
                "id": "3:20",
                "name": "Button/Done",
                "type": "INSTANCE",
                "componentId": "C:24",
                "children": [
                  {
                    "id": "3:21",
                    "name": "Label",
                    "type": "TEXT",
                    "characters": "Done"
                  }
                ]
              },
              {
                "id": "3:22",
                "name": "Icon/Checkmark",
                "type": "INSTANCE",
                "componentId": "C:25"
              }
            ]
          }
        ]
      },
      {
        "id": "9:0",
        "name": "Archive",
        "type": "CANVAS",
        "children": [
          {
            "id": "9:1",
            "name": "Old Screen",
            "type": "FRAME",
            "children": [
              {
                "id": "9:10",
                "name": "Button/Legacy",
                "type": "INSTANCE",
                "componentId": "C:99"
              }
            ]
          }
        ]
      }
    ]
  }
}
```

Key fixture properties:
- **Login page**: 2 inputs, 1 button, 1 link, 1 toggle, plus non-interactive elements (Divider, Logo). Has a dark variant frame that should be collapsed.
- **Home page**: 1 card, 2 buttons, 2 tabs, 1 bottom nav, 1 loader (excluded). Frame name has "- Default" suffix to strip.
- **Payments page**: 2 frames (Payment Form + Payment Success). Has input, dropdown, checkbox, button, and an interactive frame (prototype interaction). Also has an Icon that should be excluded.
- **Archive page**: Should be excluded entirely via config.

- [ ] **Step 2: Verify fixture loads**

Run: `uv run pytest tests/conftest.py --co -v`
Expected: conftest collected, no errors

- [ ] **Step 3: Commit**

```bash
git add tests/fixtures/banking_app.json
git commit -m "feat: add banking app Figma API response fixture"
```

---

### Task 4: Extractor — interactive element detection + screen map

**Files:**
- Create: `src/figma_taxonomy/extractor.py`
- Test: `tests/test_extractor.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_extractor.py`:
```python
import json
from pathlib import Path

import pytest

from figma_taxonomy.config import load_config
from figma_taxonomy.extractor import extract_elements
from figma_taxonomy.models import ScreenElement


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def banking_app():
    with open(FIXTURES_DIR / "banking_app.json") as f:
        return json.load(f)


@pytest.fixture
def config():
    return load_config(None)


@pytest.fixture
def elements(banking_app, config):
    return extract_elements(banking_app, config)


def test_returns_screen_elements(elements):
    assert len(elements) > 0
    assert all(isinstance(e, ScreenElement) for e in elements)


def test_detects_buttons(elements):
    buttons = [e for e in elements if e.element_type == "button"]
    names = [e.element_name for e in buttons]
    assert "log_in" in names or "Log In" in [e.text_content for e in buttons]
    assert len(buttons) >= 4  # Login, Transfer, Pay Bills, Submit, Done


def test_detects_inputs(elements):
    inputs = [e for e in elements if e.element_type == "input"]
    assert len(inputs) >= 3  # Email, Password, Amount


def test_detects_toggles(elements):
    toggles = [e for e in elements if e.element_type == "toggle"]
    assert len(toggles) >= 1  # RememberMe


def test_detects_tabs(elements):
    tabs = [e for e in elements if e.element_type == "tab"]
    assert len(tabs) >= 2  # Accounts, Cards


def test_detects_dropdowns(elements):
    dropdowns = [e for e in elements if e.element_type == "dropdown"]
    assert len(dropdowns) >= 1  # AccountSelect


def test_detects_checkboxes(elements):
    checkboxes = [e for e in elements if e.element_type == "checkbox"]
    assert len(checkboxes) >= 1  # SaveRecipient


def test_detects_links(elements):
    links = [e for e in elements if e.element_type == "link"]
    assert len(links) >= 1  # ForgotPassword


def test_detects_cards(elements):
    cards = [e for e in elements if e.element_type == "card"]
    assert len(cards) >= 1  # AccountBalance


def test_detects_interactive_frames(elements):
    """Frames with prototype interactions should be detected."""
    interactive = [e for e in elements if e.node_id == "3:18"]
    assert len(interactive) == 1
    assert interactive[0].has_interaction is True


def test_excludes_non_interactive(elements):
    """Dividers, icons, loaders, logos should be excluded."""
    node_ids = {e.node_id for e in elements}
    assert "1:18" not in node_ids  # Divider
    assert "3:22" not in node_ids  # Icon/Checkmark
    assert "2:22" not in node_ids  # Loader


def test_excludes_archive_page(elements):
    """Archive page should be excluded via config."""
    node_ids = {e.node_id for e in elements}
    assert "9:10" not in node_ids  # Button in Archive


def test_collapses_variant_frames(elements):
    """Dark variant of Login screen should not produce duplicate elements."""
    login_buttons = [
        e for e in elements
        if e.screen_name == "login_screen" and e.element_type == "button"
    ]
    # Should have exactly 1 button from login (not 2 from default + dark)
    assert len(login_buttons) == 1


def test_screen_names_cleaned(elements):
    screens = {e.screen_name for e in elements}
    # "01 - Login Screen" → "login_screen"
    assert "login_screen" in screens
    # "Home - Default" → "home"
    assert "home" in screens
    # "Payment Form" → "payment_form"
    assert "payment_form" in screens


def test_preserves_node_ids(elements):
    """Every element should have a Figma node ID for traceability."""
    assert all(e.node_id for e in elements)


def test_extracts_text_content(elements):
    buttons = [e for e in elements if e.element_type == "button"]
    texts = [e.text_content for e in buttons if e.text_content]
    assert "Log In" in texts
    assert "Transfer" in texts


def test_parent_path_populated(elements):
    login_elements = [e for e in elements if e.screen_name == "login_screen"]
    for elem in login_elements:
        assert len(elem.parent_path) >= 2  # page + frame at minimum
        assert "Login" in elem.parent_path
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_extractor.py -v`
Expected: FAIL with `ModuleNotFoundError` for `figma_taxonomy.extractor`

- [ ] **Step 3: Write the extractor implementation**

Create `src/figma_taxonomy/extractor.py`:
```python
"""Extract interactive UI elements from a Figma file tree."""

from __future__ import annotations

import re

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import ScreenElement


INTERACTIVE_PATTERNS = [
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

EXCLUDE_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [r"^icon", r"divider", r"separator", r"placeholder", r"hint", r"loader", r"spinner", r"logo"]
]

_COMPONENT_TYPES = {"COMPONENT", "COMPONENT_SET", "INSTANCE"}

_PREFIX_RE = re.compile(r"^\d+\s*[-–.]\s*")


def _is_excluded(name: str) -> bool:
    return any(pat.search(name) for pat in EXCLUDE_PATTERNS)


def _classify_element(name: str) -> str | None:
    for pattern, element_type in INTERACTIVE_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
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
            "label", "text", "title", "value",
        ):
            if child.get("characters"):
                return child["characters"]
    for child in node.get("children", []):
        if child.get("type") == "TEXT" and child.get("characters"):
            if not _is_excluded(child.get("name", "")):
                return child["characters"]
    return None


def _get_variant_base(frame_name: str, config: TaxonomyConfig) -> str:
    name = frame_name
    for suffix in config.naming.screen_name.strip_suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip().strip("-").strip()
            break
    if config.naming.screen_name.strip_prefixes:
        name = _PREFIX_RE.sub("", name)
    return name.strip()


def _find_screens(page_node: dict, config: TaxonomyConfig) -> list[dict]:
    """Return deduplicated screen frames (collapse variants)."""
    frames = [
        child for child in page_node.get("children", [])
        if child.get("type") == "FRAME"
    ]

    seen_bases: dict[str, dict] = {}
    result = []
    for frame in frames:
        base = _get_variant_base(frame["name"], config)
        if base not in seen_bases:
            seen_bases[base] = frame
            result.append(frame)

    return result


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
    is_interactive_frame = has_interaction and element_type is None

    if is_interactive_component or is_interactive_frame:
        text_content = _extract_text_content(node)

        # Clean element name: strip common prefixes
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
        return elements  # Don't recurse into interactive components

    for child in node.get("children", []):
        elements.extend(
            _walk_node(child, screen_name, page_name, parent_path, config)
        )

    return elements


def extract_elements(figma_file: dict, config: TaxonomyConfig) -> list[ScreenElement]:
    """Extract all interactive elements from a Figma file tree.

    Args:
        figma_file: Parsed JSON response from Figma GET /v1/files/:key
        config: Taxonomy configuration

    Returns:
        List of ScreenElement instances grouped by screen
    """
    document = figma_file.get("document", figma_file)
    pages = [
        child for child in document.get("children", [])
        if child.get("type") in ("CANVAS", "PAGE")
    ]

    exclude = set(config.figma.exclude_pages)

    all_elements: list[ScreenElement] = []

    for page in pages:
        page_name = page.get("name", "")
        if page_name in exclude:
            continue

        screens = _find_screens(page, config)

        for frame in screens:
            screen_name = _clean_screen_name(frame["name"], config)
            parent_path = [page_name, frame["name"]]

            all_elements.extend(
                _walk_node(frame, screen_name, page_name, parent_path, config)
            )

    return all_elements
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_extractor.py -v`
Expected: All 17 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/figma_taxonomy/extractor.py tests/test_extractor.py
git commit -m "feat: add extractor with interactive element detection and screen map builder"
```

---

### Task 5: Taxonomy naming engine

**Files:**
- Create: `src/figma_taxonomy/taxonomy_engine.py`
- Test: `tests/test_taxonomy_engine.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_taxonomy_engine.py`:
```python
import json
from pathlib import Path

import pytest

from figma_taxonomy.config import load_config
from figma_taxonomy.extractor import extract_elements
from figma_taxonomy.models import ScreenElement, TaxonomyEvent, EventProperty
from figma_taxonomy.taxonomy_engine import generate_taxonomy


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def config():
    return load_config(None)


@pytest.fixture
def elements():
    with open(FIXTURES_DIR / "banking_app.json") as f:
        figma_file = json.load(f)
    config = load_config(None)
    return extract_elements(figma_file, config)


@pytest.fixture
def taxonomy(elements, config):
    return generate_taxonomy(elements, config)


def test_returns_taxonomy_events(taxonomy):
    assert len(taxonomy) > 0
    assert all(isinstance(e, TaxonomyEvent) for e in taxonomy)


def test_generates_screen_pageview_events(taxonomy):
    """Each unique screen should get a _pageview event."""
    pageviews = [e for e in taxonomy if e.event_name.endswith("_pageview")]
    screen_names = {e.event_name.replace("_pageview", "") for e in pageviews}
    assert "login_screen" in screen_names
    assert "home" in screen_names
    assert "payment_form" in screen_names
    assert "payment_success" in screen_names


def test_button_events_use_clicked_action(taxonomy):
    button_events = [
        e for e in taxonomy
        if "clicked" in e.event_name and not e.event_name.endswith("_pageview")
    ]
    assert len(button_events) >= 1


def test_input_events_use_entered_action(taxonomy):
    input_events = [e for e in taxonomy if "entered" in e.event_name]
    assert len(input_events) >= 1


def test_toggle_events_use_toggled_action(taxonomy):
    toggle_events = [e for e in taxonomy if "toggled" in e.event_name]
    assert len(toggle_events) >= 1


def test_tab_events_use_viewed_action(taxonomy):
    tab_events = [
        e for e in taxonomy
        if "viewed" in e.event_name and not e.event_name.endswith("_pageview")
    ]
    assert len(tab_events) >= 1


def test_dropdown_events_use_selected_action(taxonomy):
    dropdown_events = [e for e in taxonomy if "selected" in e.event_name]
    assert len(dropdown_events) >= 1


def test_checkbox_events_use_checked_action(taxonomy):
    checkbox_events = [e for e in taxonomy if "checked" in e.event_name]
    assert len(checkbox_events) >= 1


def test_event_names_are_snake_case(taxonomy):
    for event in taxonomy:
        assert event.event_name == event.event_name.lower(), f"{event.event_name} is not lowercase"
        assert " " not in event.event_name, f"{event.event_name} has spaces"
        assert event.event_name.replace("_", "").isalnum(), f"{event.event_name} has invalid chars"


def test_event_names_within_length_limit(taxonomy, config):
    for event in taxonomy:
        assert len(event.event_name) <= config.naming.max_event_length


def test_events_have_flow_names(taxonomy):
    flows = {e.flow for e in taxonomy}
    assert "Login" in flows
    assert "Home" in flows
    assert "Payments" in flows


def test_events_have_descriptions(taxonomy):
    for event in taxonomy:
        assert event.description, f"{event.event_name} has no description"


def test_events_have_source_node_ids(taxonomy):
    non_pageview = [e for e in taxonomy if not e.event_name.endswith("_pageview")]
    for event in non_pageview:
        assert event.source_node_id, f"{event.event_name} has no source node ID"


def test_clicked_events_have_element_text_property(taxonomy):
    """Property rule: *_clicked → element_text."""
    clicked = [e for e in taxonomy if e.event_name.endswith("_clicked")]
    for event in clicked:
        prop_names = [p.name for p in event.properties]
        assert "element_text" in prop_names, f"{event.event_name} missing element_text"


def test_entered_events_have_field_properties(taxonomy):
    """Property rule: *_entered → field_name, is_valid."""
    entered = [e for e in taxonomy if e.event_name.endswith("_entered")]
    for event in entered:
        prop_names = [p.name for p in event.properties]
        assert "field_name" in prop_names, f"{event.event_name} missing field_name"
        assert "is_valid" in prop_names, f"{event.event_name} missing is_valid"


def test_global_properties_on_all_events(taxonomy):
    for event in taxonomy:
        prop_names = [p.name for p in event.properties]
        assert "screen_name" in prop_names, f"{event.event_name} missing screen_name"
        assert "platform" in prop_names, f"{event.event_name} missing platform"


def test_no_duplicate_event_names(taxonomy):
    names = [e.event_name for e in taxonomy]
    assert len(names) == len(set(names)), f"Duplicate events: {[n for n in names if names.count(n) > 1]}"


def test_uses_text_content_for_element_name(taxonomy):
    """Button with label 'Transfer' should produce event with 'transfer' in name."""
    transfer_events = [e for e in taxonomy if "transfer" in e.event_name]
    assert len(transfer_events) >= 1


def test_manual_element():
    """Test with a manually created ScreenElement."""
    config = load_config(None)
    elem = ScreenElement(
        node_id="99:1",
        screen_name="settings",
        element_name="BiometricLogin",
        element_type="toggle",
        text_content="Biometric Login",
        has_interaction=False,
        variants=[],
        parent_path=["Settings", "Settings Screen"],
    )
    events = generate_taxonomy([elem], config)
    # Should have 1 toggle event + 1 pageview
    toggle_events = [e for e in events if "toggled" in e.event_name]
    assert len(toggle_events) == 1
    assert "biometric" in toggle_events[0].event_name.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_taxonomy_engine.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the taxonomy engine implementation**

Create `src/figma_taxonomy/taxonomy_engine.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_taxonomy_engine.py -v`
Expected: All 20 tests pass

- [ ] **Step 5: Commit**

```bash
git add src/figma_taxonomy/taxonomy_engine.py tests/test_taxonomy_engine.py
git commit -m "feat: add taxonomy naming engine with action mapping and property rules"
```

---

### Task 6: Output formatters — Excel

**Files:**
- Create: `src/figma_taxonomy/output/excel.py`
- Test: `tests/test_output.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_output.py`:
```python
import json
from pathlib import Path

import pytest

from figma_taxonomy.config import load_config
from figma_taxonomy.extractor import extract_elements
from figma_taxonomy.models import TaxonomyEvent, EventProperty
from figma_taxonomy.taxonomy_engine import generate_taxonomy


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def config():
    return load_config(None)


@pytest.fixture
def taxonomy():
    with open(FIXTURES_DIR / "banking_app.json") as f:
        figma_file = json.load(f)
    config = load_config(None)
    elements = extract_elements(figma_file, config)
    return generate_taxonomy(elements, config)


@pytest.fixture
def sample_events():
    """Minimal hand-crafted events for output testing."""
    return [
        TaxonomyEvent(
            event_name="login_pageview",
            flow="Authentication",
            description="User views login screen",
            properties=[
                EventProperty(name="screen_name", type="string", description="Screen where event occurred"),
            ],
            source_node_id="",
        ),
        TaxonomyEvent(
            event_name="login_submit_clicked",
            flow="Authentication",
            description="User clicks submit button",
            properties=[
                EventProperty(name="element_text", type="string", description="Button text"),
                EventProperty(name="screen_name", type="string", description="Screen where event occurred"),
            ],
            source_node_id="1:14",
        ),
        TaxonomyEvent(
            event_name="payment_amount_entered",
            flow="Payments",
            description="User enters payment amount",
            properties=[
                EventProperty(name="field_name", type="string", description="Field name"),
                EventProperty(name="is_valid", type="boolean", description="Validation passed"),
                EventProperty(name="screen_name", type="string", description="Screen"),
            ],
            source_node_id="3:10",
        ),
    ]


# --- Excel tests ---

class TestExcelOutput:
    def test_creates_xlsx_file(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.excel import write_excel

        output_path = tmp_path / "taxonomy.xlsx"
        write_excel(sample_events, config, output_path)
        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_has_events_sheet(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.excel import write_excel
        import openpyxl

        output_path = tmp_path / "taxonomy.xlsx"
        write_excel(sample_events, config, output_path)

        wb = openpyxl.load_workbook(output_path)
        assert "Events" in wb.sheetnames

    def test_has_parameters_sheet(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.excel import write_excel
        import openpyxl

        output_path = tmp_path / "taxonomy.xlsx"
        write_excel(sample_events, config, output_path)

        wb = openpyxl.load_workbook(output_path)
        assert "Parameters" in wb.sheetnames

    def test_events_sheet_headers(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.excel import write_excel
        import openpyxl

        output_path = tmp_path / "taxonomy.xlsx"
        write_excel(sample_events, config, output_path)

        wb = openpyxl.load_workbook(output_path)
        ws = wb["Events"]
        headers = [ws.cell(row=2, column=c).value for c in range(2, 14)]
        assert headers[0] == "Flow"
        assert headers[1] == "Event Name"
        assert headers[2] == "Event Description"
        assert headers[3] == "Parameter Set"

    def test_events_sheet_data_rows(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.excel import write_excel
        import openpyxl

        output_path = tmp_path / "taxonomy.xlsx"
        write_excel(sample_events, config, output_path)

        wb = openpyxl.load_workbook(output_path)
        ws = wb["Events"]

        # Row 3 is first data row (row 1 empty, row 2 headers)
        assert ws.cell(row=3, column=2).value == "Authentication"
        assert ws.cell(row=3, column=3).value == "login_pageview"
        assert ws.cell(row=3, column=4).value == "User views login screen"

    def test_parameters_sheet_has_global_params(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.excel import write_excel
        import openpyxl

        output_path = tmp_path / "taxonomy.xlsx"
        write_excel(sample_events, config, output_path)

        wb = openpyxl.load_workbook(output_path)
        ws = wb["Parameters"]
        param_names = [ws.cell(row=r, column=2).value for r in range(3, 10)]
        assert "screen_name" in param_names
        assert "platform" in param_names

    def test_full_taxonomy_output(self, taxonomy, config, tmp_path):
        from figma_taxonomy.output.excel import write_excel
        import openpyxl

        output_path = tmp_path / "taxonomy.xlsx"
        write_excel(taxonomy, config, output_path)

        wb = openpyxl.load_workbook(output_path)
        ws = wb["Events"]
        # Should have header row + data rows
        data_rows = [
            ws.cell(row=r, column=3).value
            for r in range(3, ws.max_row + 1)
            if ws.cell(row=r, column=3).value
        ]
        assert len(data_rows) == len(taxonomy)


# --- CSV tests ---

class TestAmplitudeCsvOutput:
    def test_creates_csv_file(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.amplitude_csv import write_csv

        output_path = tmp_path / "taxonomy.csv"
        write_csv(sample_events, config, output_path)
        assert output_path.exists()

    def test_csv_headers(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.amplitude_csv import write_csv

        output_path = tmp_path / "taxonomy.csv"
        write_csv(sample_events, config, output_path)

        lines = output_path.read_text().strip().split("\n")
        assert lines[0] == "Event Type,Category,Description,Property Name,Property Type,Property Description"

    def test_csv_data_rows(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.amplitude_csv import write_csv

        output_path = tmp_path / "taxonomy.csv"
        write_csv(sample_events, config, output_path)

        lines = output_path.read_text().strip().split("\n")
        # Each event-property combination is a row
        assert len(lines) > 1  # header + data


# --- JSON tests ---

class TestJsonSchemaOutput:
    def test_creates_json_file(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.json_schema import write_json

        output_path = tmp_path / "taxonomy.json"
        write_json(sample_events, config, output_path)
        assert output_path.exists()

    def test_json_structure(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.json_schema import write_json

        output_path = tmp_path / "taxonomy.json"
        write_json(sample_events, config, output_path)

        data = json.loads(output_path.read_text())
        assert "$schema" in data
        assert "events" in data
        assert "login_pageview" in data["events"]
        assert "login_submit_clicked" in data["events"]

    def test_json_event_properties(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.json_schema import write_json

        output_path = tmp_path / "taxonomy.json"
        write_json(sample_events, config, output_path)

        data = json.loads(output_path.read_text())
        event = data["events"]["login_submit_clicked"]
        assert event["category"] == "Authentication"
        assert "properties" in event
        assert "element_text" in event["properties"]


# --- Markdown tests ---

class TestMarkdownOutput:
    def test_creates_md_file(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.markdown import write_markdown

        output_path = tmp_path / "taxonomy.md"
        write_markdown(sample_events, config, output_path)
        assert output_path.exists()

    def test_markdown_has_flow_headers(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.markdown import write_markdown

        output_path = tmp_path / "taxonomy.md"
        write_markdown(sample_events, config, output_path)

        content = output_path.read_text()
        assert "## Authentication" in content
        assert "## Payments" in content

    def test_markdown_has_event_sections(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.markdown import write_markdown

        output_path = tmp_path / "taxonomy.md"
        write_markdown(sample_events, config, output_path)

        content = output_path.read_text()
        assert "### login_pageview" in content
        assert "### login_submit_clicked" in content

    def test_markdown_lists_properties(self, sample_events, config, tmp_path):
        from figma_taxonomy.output.markdown import write_markdown

        output_path = tmp_path / "taxonomy.md"
        write_markdown(sample_events, config, output_path)

        content = output_path.read_text()
        assert "`element_text`" in content
        assert "`field_name`" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_output.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write Excel output formatter**

Create `src/figma_taxonomy/output/excel.py`:
```python
"""Excel output formatter matching the taxonomy template structure."""

from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.styles import Font, Alignment

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import TaxonomyEvent


def write_excel(
    events: list[TaxonomyEvent],
    config: TaxonomyConfig,
    output_path: Path,
) -> None:
    """Write taxonomy to an Excel file with Events and Parameters sheets."""
    wb = openpyxl.Workbook()

    # --- Events sheet ---
    ws_events = wb.active
    ws_events.title = "Events"

    # Row 1 is empty (matching template)
    # Row 2 is headers
    headers = [
        "", "Flow", "Event Name", "Event Description", "Parameter Set",
        "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
    ]
    for col, header in enumerate(headers, 1):
        cell = ws_events.cell(row=2, column=col, value=header)
        cell.font = Font(bold=True)

    # Data rows starting at row 3
    for i, event in enumerate(events):
        row = i + 3
        ws_events.cell(row=row, column=2, value=event.flow)
        ws_events.cell(row=row, column=3, value=event.event_name)
        ws_events.cell(row=row, column=4, value=event.description)

        # Non-global properties for the parameter set
        global_names = {p["name"] for p in config.global_properties}
        event_props = [p for p in event.properties if p.name not in global_names]

        if event_props:
            param_set = ", ".join(p.name for p in event_props)
            ws_events.cell(row=row, column=5, value=param_set)

            # Up to 4 property pairs in columns F-M
            for j, prop in enumerate(event_props[:4]):
                name_col = 6 + (j * 2)
                desc_col = 7 + (j * 2)
                ws_events.cell(row=row, column=name_col, value=prop.name)
                ws_events.cell(row=row, column=desc_col, value=prop.description)

    # --- Parameters sheet (global/UTM parameters) ---
    ws_params = wb.create_sheet("Parameters")

    # Row 1 empty, Row 2 headers
    param_headers = [
        "", "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
        "Parameter Name", "Parameter Description",
    ]
    for col, header in enumerate(param_headers, 1):
        cell = ws_params.cell(row=2, column=col, value=header)
        cell.font = Font(bold=True)

    # Write global properties
    for i, prop in enumerate(config.global_properties):
        row = i + 3
        ws_params.cell(row=row, column=2, value=prop["name"])
        ws_params.cell(row=row, column=3, value=prop.get("description", ""))

    wb.save(output_path)
```

- [ ] **Step 4: Write CSV output formatter**

Create `src/figma_taxonomy/output/amplitude_csv.py`:
```python
"""Amplitude Data CSV output formatter."""

from __future__ import annotations

import csv
from pathlib import Path

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import TaxonomyEvent


def write_csv(
    events: list[TaxonomyEvent],
    config: TaxonomyConfig,
    output_path: Path,
) -> None:
    """Write taxonomy to Amplitude-compatible CSV format."""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Event Type", "Category", "Description",
            "Property Name", "Property Type", "Property Description",
        ])

        for event in events:
            if event.properties:
                for prop in event.properties:
                    writer.writerow([
                        event.event_name,
                        event.flow,
                        event.description,
                        prop.name,
                        prop.type,
                        prop.description,
                    ])
            else:
                writer.writerow([
                    event.event_name,
                    event.flow,
                    event.description,
                    "", "", "",
                ])
```

- [ ] **Step 5: Write JSON Schema output formatter**

Create `src/figma_taxonomy/output/json_schema.py`:
```python
"""JSON Schema output formatter."""

from __future__ import annotations

import json
from pathlib import Path

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import TaxonomyEvent


def write_json(
    events: list[TaxonomyEvent],
    config: TaxonomyConfig,
    output_path: Path,
) -> None:
    """Write taxonomy to JSON Schema format."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": f"{config.app.name} Event Taxonomy",
        "events": {},
    }

    for event in events:
        properties = {}
        for prop in event.properties:
            prop_schema: dict = {"type": prop.type, "description": prop.description}
            if prop.enum_values:
                prop_schema["enum"] = prop.enum_values
            properties[prop.name] = prop_schema

        schema["events"][event.event_name] = {
            "description": event.description,
            "category": event.flow,
            "source": f"figma:node_id:{event.source_node_id}" if event.source_node_id else "",
            "properties": properties,
        }

    output_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False))
```

- [ ] **Step 6: Write Markdown output formatter**

Create `src/figma_taxonomy/output/markdown.py`:
```python
"""Markdown tracking plan output formatter."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import TaxonomyEvent


def write_markdown(
    events: list[TaxonomyEvent],
    config: TaxonomyConfig,
    output_path: Path,
) -> None:
    """Write taxonomy to a human-readable Markdown tracking plan."""
    # Group events by flow
    flows: dict[str, list[TaxonomyEvent]] = defaultdict(list)
    for event in events:
        flows[event.flow or "Other"].append(event)

    lines = [f"# {config.app.name} — Event Taxonomy", ""]

    for flow_name, flow_events in flows.items():
        lines.append(f"## {flow_name}")
        lines.append("")

        for event in flow_events:
            lines.append(f"### {event.event_name}")
            lines.append(f"- **Trigger:** {event.description}")
            if event.source_node_id:
                lines.append(f"- **Source:** Figma node `{event.source_node_id}`")

            if event.properties:
                lines.append("- **Properties:**")
                for prop in event.properties:
                    desc = f" — {prop.description}" if prop.description else ""
                    enum_str = ""
                    if prop.enum_values:
                        enum_str = f" (enum: {', '.join(prop.enum_values)})"
                    lines.append(f"  - `{prop.name}` ({prop.type}){desc}{enum_str}")
            else:
                lines.append("- **Properties:** none")

            lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 7: Run all output tests**

Run: `uv run pytest tests/test_output.py -v`
Expected: All 16 tests pass

- [ ] **Step 8: Commit**

```bash
git add src/figma_taxonomy/output/ tests/test_output.py
git commit -m "feat: add output formatters (Excel, Amplitude CSV, JSON Schema, Markdown)"
```

---

### Task 7: Figma API client

**Files:**
- Create: `src/figma_taxonomy/figma_client.py`

- [ ] **Step 1: Write the Figma client implementation**

Create `src/figma_taxonomy/figma_client.py`:
```python
"""Figma REST API client with file-version caching."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

import httpx


FIGMA_API_BASE = "https://api.figma.com/v1"
CACHE_DIR = Path(".figma-taxonomy-cache")


def _get_token() -> str:
    token = os.environ.get("FIGMA_TOKEN", "")
    if not token:
        raise RuntimeError(
            "FIGMA_TOKEN environment variable is required. "
            "Get a Personal Access Token from Figma > Settings > Access Tokens."
        )
    return token


def _parse_file_key(url_or_key: str) -> str:
    """Extract file key from a Figma URL or return raw key."""
    match = re.search(r"figma\.com/(?:file|design)/([a-zA-Z0-9]+)", url_or_key)
    if match:
        return match.group(1)

    # Check for branch URLs
    branch_match = re.search(r"figma\.com/(?:file|design)/[a-zA-Z0-9]+/branch/([a-zA-Z0-9]+)", url_or_key)
    if branch_match:
        return branch_match.group(1)

    # Assume it's a raw file key
    return url_or_key


def _cache_path(file_key: str, version: str) -> Path:
    key = hashlib.sha256(f"{file_key}:{version}".encode()).hexdigest()[:16]
    return CACHE_DIR / f"{file_key}_{key}.json"


def _read_cache(file_key: str, version: str) -> dict | None:
    path = _cache_path(file_key, version)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def _write_cache(file_key: str, version: str, data: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(file_key, version)
    with open(path, "w") as f:
        json.dump(data, f)


def fetch_file(url_or_key: str, no_cache: bool = False) -> dict:
    """Fetch a Figma file tree.

    Args:
        url_or_key: Figma file URL or raw file key
        no_cache: If True, skip cache and always fetch from API

    Returns:
        Parsed JSON response from Figma GET /v1/files/:key
    """
    file_key = _parse_file_key(url_or_key)
    token = _get_token()

    headers = {"X-FIGMA-TOKEN": token}

    # First, get file metadata to check version
    if not no_cache:
        with httpx.Client() as client:
            meta_resp = client.get(
                f"{FIGMA_API_BASE}/files/{file_key}",
                headers=headers,
                params={"depth": 1},
            )
            meta_resp.raise_for_status()
            meta = meta_resp.json()
            version = meta.get("version", "")

            cached = _read_cache(file_key, version)
            if cached is not None:
                return cached

    # Fetch full file tree
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(
            f"{FIGMA_API_BASE}/files/{file_key}",
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    # Cache the result
    version = data.get("version", "unknown")
    _write_cache(file_key, version, data)

    return data


def load_fixture(path: Path) -> dict:
    """Load a Figma API response from a local JSON file."""
    with open(path) as f:
        return json.load(f)
```

- [ ] **Step 2: Commit**

```bash
git add src/figma_taxonomy/figma_client.py
git commit -m "feat: add Figma API client with file-version caching"
```

---

### Task 8: CLI entrypoint

**Files:**
- Create: `src/figma_taxonomy/cli.py`

- [ ] **Step 1: Write the CLI implementation**

Create `src/figma_taxonomy/cli.py`:
```python
"""CLI entrypoint for figma-taxonomy-gen."""

from __future__ import annotations

from pathlib import Path

import click

from figma_taxonomy.config import load_config
from figma_taxonomy.extractor import extract_elements
from figma_taxonomy.figma_client import fetch_file, load_fixture
from figma_taxonomy.taxonomy_engine import generate_taxonomy


@click.group()
@click.version_option()
def main():
    """Extract interactive UI elements from Figma designs and generate Amplitude event taxonomies."""
    pass


@main.command()
@click.argument("figma_url", required=False)
@click.option("--fixture", type=click.Path(exists=True, path_type=Path), help="Use a local JSON fixture instead of Figma API")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True, path_type=Path), help="Path to taxonomy.config.yaml")
@click.option("--output", "-o", "output_dir", type=click.Path(path_type=Path), default="./output", help="Output directory")
@click.option("--format", "-f", "formats", default="excel,csv,json,markdown", help="Comma-separated output formats")
@click.option("--page", help="Extract only a specific page by name")
@click.option("--no-cache", is_flag=True, help="Skip Figma API cache")
def extract(figma_url, fixture, config_path, output_dir, formats, page, no_cache):
    """Extract taxonomy from a Figma file.

    Pass a Figma URL to fetch from the API, or use --fixture for a local JSON file.
    """
    if not figma_url and not fixture:
        raise click.UsageError("Provide a Figma URL or use --fixture with a local JSON file.")

    # Load config
    config = load_config(config_path)

    # Fetch Figma file
    if fixture:
        click.echo(f"Loading fixture: {fixture}")
        figma_file = load_fixture(fixture)
    else:
        click.echo(f"Fetching Figma file: {figma_url}")
        figma_file = fetch_file(figma_url, no_cache=no_cache)

    # Filter to specific page if requested
    if page:
        config.figma.exclude_pages = []  # Clear excludes when targeting specific page
        document = figma_file.get("document", figma_file)
        matching = [
            child for child in document.get("children", [])
            if child.get("name") == page
        ]
        if not matching:
            available = [c.get("name") for c in document.get("children", [])]
            raise click.ClickException(f"Page '{page}' not found. Available: {available}")
        figma_file = {"document": {"children": matching}}

    # Extract elements
    click.echo("Extracting interactive elements...")
    elements = extract_elements(figma_file, config)
    click.echo(f"Found {len(elements)} interactive elements")

    # Generate taxonomy
    click.echo("Generating taxonomy...")
    events = generate_taxonomy(elements, config)
    click.echo(f"Generated {len(events)} events")

    # Write outputs
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    format_list = [f.strip() for f in formats.split(",")]

    if "excel" in format_list:
        from figma_taxonomy.output.excel import write_excel
        path = output_dir / "taxonomy.xlsx"
        write_excel(events, config, path)
        click.echo(f"  Excel:    {path}")

    if "csv" in format_list:
        from figma_taxonomy.output.amplitude_csv import write_csv
        path = output_dir / "taxonomy.csv"
        write_csv(events, config, path)
        click.echo(f"  CSV:      {path}")

    if "json" in format_list:
        from figma_taxonomy.output.json_schema import write_json
        path = output_dir / "taxonomy.json"
        write_json(events, config, path)
        click.echo(f"  JSON:     {path}")

    if "markdown" in format_list:
        from figma_taxonomy.output.markdown import write_markdown
        path = output_dir / "taxonomy.md"
        write_markdown(events, config, path)
        click.echo(f"  Markdown: {path}")

    click.echo(f"\nDone! {len(events)} events written to {output_dir}/")
```

- [ ] **Step 2: Test CLI with fixture**

```bash
uv run figma-taxonomy extract --fixture tests/fixtures/banking_app.json --output ./output-test
```

Expected output:
```
Loading fixture: tests/fixtures/banking_app.json
Extracting interactive elements...
Found NN interactive elements
Generating taxonomy...
Generated NN events
  Excel:    output-test/taxonomy.xlsx
  CSV:      output-test/taxonomy.csv
  JSON:     output-test/taxonomy.json
  Markdown: output-test/taxonomy.md

Done! NN events written to output-test/
```

- [ ] **Step 3: Verify outputs**

```bash
cat output-test/taxonomy.md | head -40
cat output-test/taxonomy.csv | head -10
python -c "import json; d=json.load(open('output-test/taxonomy.json')); print(len(d['events']), 'events'); print(list(d['events'].keys())[:5])"
```

- [ ] **Step 4: Clean up test output and commit**

```bash
rm -rf output-test
git add src/figma_taxonomy/cli.py
git commit -m "feat: add CLI entrypoint with extract command"
```

---

### Task 9: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

Create `README.md`:
````markdown
# figma-taxonomy-gen

CLI tool that extracts interactive UI elements from Figma designs and generates an opinionated [Amplitude](https://amplitude.com) event taxonomy.

**Problem:** Every team building a tracking plan goes through the same cycle — designer creates screens, PM manually writes a spreadsheet, analyst maps events, developer implements tracking, nobody keeps it in sync. This tool closes the gap between "design is done" and "tracking plan exists."

## What it does

```
Figma file → Extract interactive elements → Apply naming conventions → Output taxonomy
```

1. Fetches your Figma file via the REST API (or reads a local JSON fixture)
2. Walks the node tree and identifies interactive elements (buttons, inputs, toggles, tabs, cards, modals, etc.)
3. Builds a screen map from the page/frame hierarchy
4. Generates events using configurable naming conventions (`{screen}_{element}_{action}`)
5. Applies property rules (e.g., all `*_fail` events get `error_description`)
6. Outputs to Excel, Amplitude CSV, JSON Schema, and Markdown

## Installation

```bash
# With uv (recommended)
uv pip install figma-taxonomy-gen

# Or with pip
pip install figma-taxonomy-gen
```

### From source

```bash
git clone https://github.com/arcbaslow/figma-taxonomy-gen
cd figma-taxonomy-gen
uv sync
```

## Quick start

### From a Figma file

```bash
export FIGMA_TOKEN="your-figma-personal-access-token"
figma-taxonomy extract https://figma.com/file/ABC123/MyApp
```

### From a local fixture (no token needed)

```bash
figma-taxonomy extract --fixture tests/fixtures/banking_app.json
```

### Output

By default, four files are generated in `./output/`:

| File | Format | Use case |
|------|--------|----------|
| `taxonomy.xlsx` | Excel | Team review, matches common tracking plan templates |
| `taxonomy.csv` | Amplitude CSV | Import directly into Amplitude Data |
| `taxonomy.json` | JSON Schema | Validation, CI/CD, custom tooling |
| `taxonomy.md` | Markdown | PR reviews, wiki, documentation |

## CLI reference

```bash
# Basic extraction
figma-taxonomy extract https://figma.com/file/ABC123/MyApp

# Custom output directory
figma-taxonomy extract https://figma.com/file/ABC123/MyApp --output ./my-output

# Specific formats only
figma-taxonomy extract ... --format excel,csv

# Specific page only
figma-taxonomy extract ... --page "Onboarding"

# Custom config
figma-taxonomy extract ... --config ./my-config.yaml

# Skip API cache
figma-taxonomy extract ... --no-cache
```

## Configuration

Create a `taxonomy.config.yaml` to customize naming conventions:

```yaml
app:
  type: fintech
  name: "MyApp"

naming:
  style: snake_case
  pattern: "{screen}_{element}_{action}"
  max_event_length: 64

  actions:
    button: "clicked"
    input: "entered"
    toggle: "toggled"
    tab: "viewed"
    screen: "pageview"

  screen_name:
    strip_prefixes: true
    strip_suffixes: ["- Default", "- Light", "- Dark"]

output:
  formats: ["excel", "csv", "json", "markdown"]
  directory: "./output"
```

See [`taxonomy.config.yaml`](taxonomy.config.yaml) for the full default config with all options.

## How element detection works

The tool uses a three-layer strategy to identify interactive elements:

1. **Name patterns** — Matches component names against known patterns (`button`, `input`, `toggle`, `dropdown`, etc.)
2. **Prototype interactions** — Any node with a Figma interaction (click, hover, drag) is automatically interactive
3. **Component types** — Only `COMPONENT`, `COMPONENT_SET`, and `INSTANCE` nodes are considered

Non-interactive elements (icons, dividers, loaders, placeholders) are automatically excluded.

## Naming convention

Events follow the `{screen}_{element}_{action}` pattern:

| Figma structure | Generated event |
|----------------|----------------|
| Page "Login" → Frame "01 - Login Screen" → Button "Log In" | `login_screen_log_in_clicked` |
| Page "Home" → Frame "Home - Default" → Tab "Accounts" | `home_accounts_viewed` |
| Page "Payments" → Frame "Payment Form" → Input "Amount" | `payment_form_amount_entered` |

Screen names are cleaned automatically (numbered prefixes stripped, variant suffixes collapsed).

## Property rules

Configure automatic property assignment based on event name patterns:

```yaml
property_rules:
  - match: "*_clicked"
    add:
      - name: "element_text"
        type: "string"
  - match: "*_fail"
    add:
      - name: "error_description"
        type: "string"
```

Global properties (like `screen_name`, `platform`) are added to every event.

## Development

```bash
git clone https://github.com/arcbaslow/figma-taxonomy-gen
cd figma-taxonomy-gen
uv sync

# Run tests
uv run pytest -v

# Run CLI
uv run figma-taxonomy extract --fixture tests/fixtures/banking_app.json
```

## Roadmap

- [x] **v0.1** — Core extraction pipeline, CLI, 4 output formats
- [ ] **v0.2** — Full config support, `validate` command (taxonomy drift detection)
- [ ] **v0.3** — AI enrichment via Claude (property inference from screen context)
- [ ] **v0.4** — MCP server for Claude Desktop, Amplitude API push, `diff` command
- [ ] **v1.0** — CI integration, documentation site, PyPI publish

## License

MIT
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with usage guide, CLI reference, and roadmap"
```

---

### Task 10: Run full test suite and generate example outputs

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass across test_models, test_config, test_extractor, test_taxonomy_engine, test_output.

- [ ] **Step 2: Generate example outputs**

```bash
mkdir -p examples/banking-app
uv run figma-taxonomy extract --fixture tests/fixtures/banking_app.json --output examples/banking-app
```

- [ ] **Step 3: Commit examples**

```bash
git add examples/
git commit -m "docs: add banking-app example outputs"
```

- [ ] **Step 4: Push to GitHub**

```bash
git push origin main
```
