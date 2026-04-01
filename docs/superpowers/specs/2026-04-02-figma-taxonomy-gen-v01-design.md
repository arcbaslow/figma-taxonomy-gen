# figma-taxonomy-gen v0.1 — Design Spec

**Date:** 2026-04-02
**Scope:** End-to-end core pipeline (Figma extraction → naming engine → multi-format output)
**Approach:** Modular library + CLI (Approach B)

---

## Overview

CLI tool that extracts interactive UI elements from Figma designs and generates an opinionated Amplitude event taxonomy. v0.1 covers the core pipeline with test fixtures, live Figma API client, configurable naming conventions, and four output formats (Excel, CSV, JSON, Markdown).

---

## Architecture

```
Figma File URL or fixture JSON
    │
    ▼
  figma_client.py    →  Fetch file tree via REST API, cache by version
    │
    ▼
  extractor.py       →  Walk node tree, filter interactive elements, build screen map
    │
    ▼
  taxonomy_engine.py →  Apply naming conventions, generate events + properties
    │
    ▼
  output/            →  Format as Excel / Amplitude CSV / JSON Schema / Markdown
```

### Project Structure

```
figma-taxonomy-gen/
├── CLAUDE.md
├── README.md
├── LICENSE                      # MIT
├── taxonomy.config.yaml         # Default config
├── pyproject.toml               # uv/pip, Python 3.11+
│
├── src/
│   └── figma_taxonomy/
│       ├── __init__.py
│       ├── cli.py               # Click CLI entrypoint
│       ├── figma_client.py      # Figma REST API wrapper + caching
│       ├── extractor.py         # Node tree walker + interactive element filter
│       ├── taxonomy_engine.py   # Naming convention engine + event generator
│       ├── config.py            # Config loader (YAML → dataclass)
│       └── output/
│           ├── __init__.py
│           ├── excel.py         # .xlsx matching template structure
│           ├── amplitude_csv.py # Amplitude Data import CSV
│           ├── json_schema.py   # JSON Schema output
│           └── markdown.py      # Human-readable tracking plan
│
├── tests/
│   ├── conftest.py
│   ├── fixtures/
│   │   └── banking-app.json     # Realistic Figma API response fixture
│   ├── test_extractor.py
│   ├── test_taxonomy_engine.py
│   └── test_output.py
│
└── examples/
    └── banking-app/             # Example output files
```

### Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11+ | Target audience knows Python |
| Package manager | uv | Fast, modern. Fallback to pip. |
| CLI | click | Standard, well-documented |
| HTTP | httpx | Async support for Figma API batching |
| Config | PyYAML | Human-editable taxonomy.config.yaml |
| Excel output | openpyxl | Write .xlsx matching template structure |
| Testing | pytest | Standard |

---

## Data Types

```python
@dataclass
class ScreenElement:
    node_id: str              # Figma node ID for traceability
    screen_name: str          # Cleaned frame/page name
    element_name: str         # Component name or text content
    element_type: str         # button, input, toggle, etc.
    text_content: str | None  # Visible label text
    has_interaction: bool     # Has prototype interaction
    variants: list[str]       # Component variant names
    parent_path: list[str]    # Full hierarchy path

@dataclass
class TaxonomyEvent:
    event_name: str           # e.g. "login_pageview"
    flow: str                 # e.g. "Authentication"
    description: str          # Human-readable description
    properties: list[EventProperty]
    source_node_id: str       # Back-reference to Figma

@dataclass
class EventProperty:
    name: str
    type: str                 # string, number, boolean, enum
    description: str
    enum_values: list[str] | None
```

---

## Interactive Element Detection

Three-layer detection strategy:

### Layer 1 — Name pattern matching

```python
INTERACTIVE_PATTERNS = [
    r"button", r"btn", r"cta",
    r"link", r"anchor",
    r"input", r"field", r"text.?field", r"search.?bar",
    r"toggle", r"switch",
    r"checkbox", r"check.?box",
    r"radio",
    r"dropdown", r"select", r"picker",
    r"tab", r"tab.?bar",
    r"card",
    r"modal", r"dialog", r"sheet",
    r"nav.?bar", r"bottom.?nav",
    r"carousel", r"slider",
    r"chip", r"tag", r"badge",
]

EXCLUDE_PATTERNS = [
    r"icon", r"divider", r"separator",
    r"placeholder", r"hint",
    r"loader", r"spinner",
]
```

### Layer 2 — Prototype interactions

Any node with a Figma interaction (click, hover, drag) is automatically interactive regardless of name.

### Layer 3 — Component type check

Only `COMPONENT`, `COMPONENT_SET`, and `INSTANCE` nodes are considered. Raw frames/groups are skipped unless they have prototype interactions.

### Screen map construction

- Top-level frames within pages = screens
- Variant detection: frames with same base name but different suffixes (`- Default`, `- Dark`, `- Skeleton`) collapse into one screen
- Frame numbering stripped: `"01 - Welcome"` → `"welcome"`
- Page name becomes the flow name
- Configurable via `taxonomy.config.yaml`

---

## Naming Convention Engine

### Transformation pipeline

```
Page: "Onboarding" + Frame: "02 - Phone Input" + Component: "Input/Phone"
  → screen: "onboarding_phone"
  → element: "phone"
  → action: "entered" (from input type mapping)
  → event: "onboarding_phone_entered"
  → flow: "Onboarding"
```

### Action mapping (configurable)

| Element type | Default action |
|---|---|
| button, link | `clicked` |
| input, field | `entered` |
| toggle, switch | `toggled` |
| checkbox | `checked` |
| dropdown, select | `selected` |
| tab | `viewed` |
| card | `viewed` / `clicked` (if has interaction) |
| modal, dialog | `opened` |
| form | `submitted` |
| screen (auto-generated) | `pageview` |

### Name cleaning

1. Strip design-system prefixes: `"Component/"`, `"UI/"`, `"Atoms/"`, etc.
2. Prefer text content over component name (button label > component name)
3. Convert to snake_case
4. Enforce max 64 chars (Amplitude limit)

### Auto-generated screen events

For every unique screen, a `{screen}_pageview` event is automatically generated.

### Property rules (pattern-matched from config)

| Pattern | Auto-added properties |
|---|---|
| `*_clicked` | `element_text` (string) |
| `*_entered` | `field_name` (string), `is_valid` (boolean) |
| `*_fail` | `error_description` (string) |
| `*_payment_success` | `insurance_premium` (string), `card_type` (string) |
| Global (all events) | `screen_name`, `platform`, `app_version` |

---

## Output Formats

### 1. Excel (.xlsx)

Matches the taxonomy template structure:

**Sheet "События" (Events):**

| Column | Content |
|--------|---------|
| B | Flow name |
| C | Event name |
| D | Event description |
| E | Parameter set (comma-separated names) |
| F-M | Up to 4 parameter name/description pairs |

**Sheet "Параметры" (Parameters):**

| Column | Content |
|--------|---------|
| B | Parameter name |
| C | Parameter description |

Row 1 is empty, Row 2 is headers.

### 2. Amplitude CSV

```csv
Event Type,Category,Description,Property Name,Property Type,Property Description
login_pageview,Authentication,User views login screen,screen_name,string,Screen where event occurred
```

### 3. JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "events": {
    "login_pageview": {
      "description": "User views login screen",
      "category": "Authentication",
      "source": "figma:node_id:1234",
      "properties": { ... }
    }
  }
}
```

### 4. Markdown

```markdown
## Authentication

### login_pageview
- **Trigger:** User views login screen
- **Source:** Figma frame "Login"
- **Properties:** none
```

---

## Figma API Client

### Authentication

- Personal Access Token via `FIGMA_TOKEN` env var

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/files/:key` | Full file tree |
| `GET /v1/files/:key/nodes?ids=...` | Specific subtrees (batched, max 50 IDs) |

### Caching

- Cache in `.figma-taxonomy-cache/` keyed by file version
- Invalidate via `lastModified` from file metadata
- `--no-cache` flag to force fresh fetch

### Node fields extracted

- `id`, `name`, `type`, `characters` (text content)
- `children`, `componentId`, `interactions`, `componentProperties`

---

## CLI Interface

```bash
# Extract from live Figma file
figma-taxonomy extract https://figma.com/file/ABC123/MyApp --output ./output

# Extract from fixture (no token needed)
figma-taxonomy extract --fixture ./tests/fixtures/banking-app.json

# Specific page only
figma-taxonomy extract https://figma.com/file/ABC123/MyApp --page "Onboarding"

# Choose output formats (default: all)
figma-taxonomy extract ... --format excel,csv,json,markdown

# Custom config
figma-taxonomy extract ... --config ./my-config.yaml

# No cache
figma-taxonomy extract ... --no-cache
```

---

## Configuration

Default `taxonomy.config.yaml`:

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
      - name: "is_valid"
        type: "boolean"
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

---

## Test Strategy

- **Fixtures:** Realistic Figma API response JSON for a banking app (sanitized, English)
- **test_extractor.py:** Verifies interactive element detection, screen map construction, variant collapsing
- **test_taxonomy_engine.py:** Verifies naming conventions, action mapping, property rules
- **test_output.py:** Verifies each output format produces correct structure
- No live API calls in tests — all fixture-based

---

## Out of Scope for v0.1

- AI enrichment (Claude API) — v0.3
- MCP server — v0.4
- Amplitude Taxonomy API push — v0.4
- `validate` command (drift detection) — v0.2
- `diff` command — v0.4
- Figma plugin companion — v1.0
