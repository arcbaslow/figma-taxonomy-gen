# CLAUDE.md

## Project: `figma-taxonomy-gen`

**One-line:** CLI + MCP tool that extracts interactive UI elements from Figma designs and generates an opinionated Amplitude event taxonomy - with optional AI-powered event naming and property inference.

---

## Problem

Every fintech/e-commerce team building an Amplitude (or Mixpanel/PostHog) tracking plan goes through the same painful cycle:

1. Designer creates screens in Figma
2. Product manager manually writes a tracking plan spreadsheet
3. Analyst maps events to business metrics
4. Developer implements tracking code
5. Nobody keeps the spreadsheet in sync - taxonomy drifts

Existing tools (Amplitude Event Planner plugin, Tracking Plan Companion, Avo) address pieces of this, but none automate the initial extraction. They all require manual annotation of Figma designs. The Amplitude Taxonomy API exists but is Enterprise-only and doesn't connect to design files.

**This tool closes the gap between "design is done" and "tracking plan exists."**

---

## What it does

### Core flow

```
Figma file URL
    |
    v
[1] Figma REST API: extract all pages, frames, components
    |
    v
[2] Filter: keep only interactive elements
    (buttons, links, inputs, toggles, tabs, forms, cards, modals)
    |
    v
[3] Build screen map: group elements by page/frame hierarchy
    |
    v
[4] Generate taxonomy using naming convention rules
    |
    v
[5] (Optional) LLM pass: infer event properties from context
    |
    v
[6] Output: JSON schema + Amplitude CSV + tracking plan markdown
```

### Naming convention engine

The tool applies an opinionated, configurable naming convention:

```
{object}_{action}
```

Examples from a banking app:
- `button/Apply Now` on `Loan Details` screen -> `loan_apply_started`
- `input/Phone` on `Registration` screen -> `registration_phone_entered`
- `toggle/Biometric Login` on `Settings` screen -> `settings_biometric_toggled`
- `tab/History` on `Account` screen -> `account_history_viewed`
- `card/Product Offer` on `Home` screen -> `home_offer_viewed`

Convention is configurable via `taxonomy.config.yaml`.

### AI-powered property inference (optional)

When `--ai` flag is passed, the tool sends the screen context (component name, parent frame, sibling elements, screen purpose) to Claude API to infer:
- Event properties (e.g., `loan_type`, `product_id`, `toggle_state`)
- Property types (string, number, boolean, enum)
- Suggested enum values based on component variants
- Business category assignment

---

## Architecture

```
figma-taxonomy-gen/
├── CLAUDE.md                    # This file
├── README.md                    # User-facing docs
├── LICENSE                      # MIT
├── taxonomy.config.yaml         # Naming convention + rules
├── pyproject.toml               # Python package config (uv/pip)
│
├── src/
│   └── figma_taxonomy/
│       ├── __init__.py
│       ├── cli.py               # CLI entrypoint (click)
│       ├── config.py            # Config loader + typed dataclasses
│       ├── models.py            # ScreenElement, TaxonomyEvent, EventProperty
│       ├── figma_client.py      # Figma REST API wrapper with file-version cache
│       ├── extractor.py         # Node tree walker + interactive element filter
│       ├── taxonomy_engine.py   # Naming convention engine + event generator
│       ├── ai_enricher.py       # Claude API integration for property inference
│       ├── validate.py          # Drift detection (taxonomy vs Figma)
│       ├── amplitude_push.py    # Amplitude Taxonomy API push (Enterprise)
│       ├── mcp_server.py        # MCP server entrypoint (figma-taxonomy-mcp)
│       ├── mcp_tools.py         # Pure-function MCP tool implementations
│       └── output/
│           ├── amplitude_csv.py # Amplitude Data CSV format
│           ├── excel.py         # .xlsx matching tracking-plan template
│           ├── json_schema.py   # JSON Schema output
│           └── markdown.py      # Human-readable tracking plan
│
├── tests/
│   ├── fixtures/                # Sample Figma API responses
│   ├── conftest.py
│   ├── test_extractor.py
│   ├── test_taxonomy_engine.py
│   ├── test_output.py
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_ai_enricher.py
│   ├── test_amplitude_push.py
│   ├── test_validate.py
│   ├── test_mcp_tools.py
│   └── test_diff.py
│
└── examples/
    ├── banking-app/             # Example: fintech app taxonomy
    ├── ecommerce/               # Example: e-commerce taxonomy
    └── saas-dashboard/          # Example: SaaS product taxonomy
```

The MCP server lives inside the package (`src/figma_taxonomy/mcp_server.py`) rather than
a separate top-level `mcp/` directory, so it ships with `pip install figma-taxonomy-gen[mcp]`
and is exposed as the `figma-taxonomy-mcp` console script declared in `pyproject.toml`.

---

## Tech stack

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11+ | Target audience (analysts, growth teams) already knows Python. Airflow/data ecosystem alignment. |
| Package manager | uv | Fast, modern, good DX. Fallback to pip. |
| CLI framework | click | Standard, well-documented. |
| HTTP client | httpx | Async support for Figma API batching. |
| Config | PyYAML | taxonomy.config.yaml is human-editable. |
| AI | anthropic SDK | Claude for property inference. Optional dependency. |
| MCP | mcp SDK | For Claude Desktop / claude.ai integration. |
| Testing | pytest | Standard. |
| Output formats | csv, json, markdown | No heavy dependencies. |

---

## Key design decisions

### 1. Interactive element detection

Figma nodes don't have a semantic "this is a button" flag. Detection relies on heuristics:

```python
INTERACTIVE_HEURISTICS = {
    # By component name patterns (case-insensitive)
    "name_patterns": [
        r"button", r"btn", r"cta",
        r"link", r"anchor",
        r"input", r"field", r"text.?field", r"search.?bar",
        r"toggle", r"switch",
        r"checkbox", r"check.?box",
        r"radio",
        r"dropdown", r"select", r"picker",
        r"tab", r"tab.?bar",
        r"card",                           # clickable cards
        r"modal", r"dialog", r"sheet",     # screen-level events
        r"nav.?bar", r"bottom.?nav",       # navigation events
        r"carousel", r"slider",
        r"chip", r"tag", r"badge",         # filterable elements
    ],

    # By Figma node properties
    "has_interaction": True,               # nodes with prototype interactions
    "component_types": ["COMPONENT", "COMPONENT_SET", "INSTANCE"],

    # Exclude patterns (not interactive despite matching above)
    "exclude_patterns": [
        r"icon",                           # icons inside buttons, not standalone
        r"divider", r"separator",
        r"placeholder", r"hint",
        r"loader", r"spinner",
    ],
}
```

Additionally, any node with a **prototype interaction** (click, hover, drag) attached is automatically classified as interactive regardless of name.

### 2. Screen context inference

The tool builds a screen map from the Figma frame hierarchy:

```
Page: "Onboarding"
  Frame: "01 - Welcome"        -> screen: onboarding_welcome
  Frame: "02 - Phone Input"    -> screen: onboarding_phone
  Frame: "03 - OTP"            -> screen: onboarding_otp
  Frame: "04 - Success"        -> screen: onboarding_success

Page: "Home"
  Frame: "Home - Default"      -> screen: home
  Frame: "Home - With Offer"   -> screen: home (variant, not separate screen)
```

Frame naming conventions are configurable. The tool detects variant frames (same screen, different states) and collapses them.

### 3. Naming convention engine

Default convention follows the `{screen}_{object}_{action}` pattern:

```yaml
# taxonomy.config.yaml
naming:
  style: snake_case          # snake_case | camelCase | Title Case
  pattern: "{screen}_{element}_{action}"
  
  # Action mapping: component type -> default action verb
  actions:
    button: "clicked"
    link: "clicked"
    input: "entered"         # or "focused" / "submitted"
    toggle: "toggled"
    checkbox: "checked"
    dropdown: "selected"
    tab: "viewed"
    card: "viewed"           # or "clicked" if has interaction
    modal: "opened"
    form: "submitted"
    screen: "viewed"         # auto-generated for each screen

  # Screen name cleaning
  screen_name:
    strip_prefixes: true     # remove "01 - ", "Step 1:", etc.
    strip_suffixes: ["- Default", "- Light", "- Dark"]
    max_depth: 2             # how deep into frame hierarchy for screen name

  # Element name cleaning  
  element_name:
    strip_common: ["Component/", "UI/", "Atoms/", "Molecules/"]
    use_text_content: true   # prefer button label over component name
```

### 4. Output formats

**Amplitude CSV** (importable via Amplitude Data):
```csv
Event Type,Category,Description,Property Name,Property Type,Property Description
onboarding_phone_entered,Onboarding,User enters phone number on onboarding screen,phone_format,string,Format of phone entered (with/without country code)
onboarding_phone_entered,Onboarding,User enters phone number on onboarding screen,screen_name,string,Screen where event occurred
```

**JSON Schema** (for validation, Ampli CLI, or custom tooling):
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "events": {
    "onboarding_phone_entered": {
      "description": "User enters phone number on onboarding screen",
      "category": "Onboarding",
      "source": "figma:node_id:1234",
      "properties": {
        "phone_format": { "type": "string", "enum": ["local", "international"] },
        "screen_name": { "type": "string" }
      }
    }
  }
}
```

**Markdown tracking plan** (for team review, PRs, wiki):
```markdown
## Onboarding

### onboarding_welcome_viewed
- **Trigger:** User lands on welcome screen
- **Source:** Figma frame "01 - Welcome"
- **Properties:** none

### onboarding_phone_entered
- **Trigger:** User enters phone number
- **Source:** Figma component "Input/Phone" in frame "02 - Phone Input"
- **Properties:**
  - `phone_format` (string) - Format of phone entered
```

### 5. MCP integration

The tool exposes an MCP server so Claude Desktop / claude.ai can use it as a tool:

```python
# MCP tools exposed:
# 1. extract_taxonomy(figma_url, config?) -> full taxonomy JSON
# 2. suggest_events(figma_url, screen_name?) -> AI-suggested events for a screen
# 3. validate_taxonomy(taxonomy_json) -> validation report
# 4. export_taxonomy(taxonomy_json, format) -> CSV/JSON/MD output
```

This means a user can say to Claude: "Look at my Figma file and generate a tracking plan" and Claude will call the tool, get structured data, and present it conversationally.

---

## Figma API usage

### Authentication
- Personal Access Token (PAT) via env var `FIGMA_TOKEN`
- OAuth2 flow for MCP server (future)

### Endpoints used
| Endpoint | Purpose | Rate limit |
|----------|---------|------------|
| `GET /v1/files/:key` | Full file tree with all nodes | Tier 1, ~60 req/min |
| `GET /v1/files/:key/nodes?ids=...` | Specific node subtrees (batched, max 50 IDs) | Tier 1 |
| `GET /v1/files/:key/images` | Screenshots for documentation | Tier 2 |

### Key node types and what we extract

```python
# From each node, we extract:
NODE_FIELDS = {
    "id": str,               # Figma node ID (for traceability)
    "name": str,             # Component/layer name
    "type": str,             # FRAME, COMPONENT, INSTANCE, TEXT, etc.
    "characters": str,       # Text content (for buttons, labels)
    "children": list,        # Child nodes (recursive)
    "componentId": str,      # Links instance to main component
    "interactions": list,    # Prototype interactions (click targets)
    "componentProperties": dict,  # Variant properties
}
```

### Caching
- File tree is cached locally (`.figma-taxonomy-cache/`) keyed by file version
- Cache invalidation via `lastModified` from file metadata
- `--no-cache` flag to force fresh fetch

---

## Amplitude Taxonomy API integration

**Note:** The Taxonomy API is Enterprise-only and was built for the older "Govern" product. As of 2024-2025, it has limited support with the newer "Amplitude Data" tracking plans. The tool primarily outputs CSV for import, but supports direct API push for Enterprise users.

### API endpoints used
| Endpoint | Purpose |
|----------|---------|
| `POST /api/2/taxonomy/category` | Create event categories |
| `POST /api/2/taxonomy/event` | Create event types |
| `POST /api/2/taxonomy/event-property` | Create event properties |
| `GET /api/2/taxonomy/event` | List existing events (for dedup) |

### Auth
- Basic auth: `{api_key}:{secret_key}` base64-encoded
- Env vars: `AMPLITUDE_API_KEY`, `AMPLITUDE_SECRET_KEY`

---

## AI enrichment (Claude)

When `--ai` or `--enrich` flag is passed:

1. Batch screen contexts (screen name + list of components + text content)
2. Send to Claude with a structured prompt requesting JSON output
3. Claude infers:
   - Event property names and types
   - Enum values from component variants
   - Business-relevant descriptions
   - Category assignments
4. Merge AI suggestions with rule-based taxonomy
5. Human reviews via markdown diff or interactive CLI

### Prompt structure

```
You are a product analytics expert specializing in fintech event taxonomies.

Given the following Figma screen context, suggest event properties for each interactive element.

Screen: {screen_name}
App type: {app_type from config}
Elements:
{list of interactive elements with names, types, text content, variants}

Respond in JSON only. Schema: ...
```

### Cost control
- Claude Haiku for bulk inference (cheap, fast)
- Claude Sonnet for complex screens with many variants
- Estimated cost: ~$0.02-0.05 per screen (Haiku), ~$0.10-0.20 per screen (Sonnet)
- Full banking app (30-50 screens): $0.50-2.00 total

---

## Configuration reference

```yaml
# taxonomy.config.yaml

app:
  type: fintech              # fintech | ecommerce | saas | social | media
  name: "MyBank"
  
figma:
  file_key: ""               # or pass via CLI --file-key
  exclude_pages: ["Archive", "Drafts", "Components"]
  
naming:
  style: snake_case
  pattern: "{screen}_{element}_{action}"
  max_event_length: 64       # Amplitude limit
  
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
    screen: "viewed"
    
  screen_name:
    strip_prefixes: true
    strip_suffixes: ["- Default", "- Light", "- Dark", "- Skeleton"]
    max_depth: 2
    
  element_name:
    strip_common: ["Component/", "UI/", "Atoms/", "Molecules/", "Organisms/"]
    use_text_content: true
    fallback_to_component_name: true

output:
  formats: ["json", "csv", "markdown"]
  directory: "./output"
  include_screenshots: false   # fetch frame images for markdown docs
  
amplitude:
  push_to_api: false           # requires Enterprise
  api_key: ""                  # or env AMPLITUDE_API_KEY
  secret_key: ""               # or env AMPLITUDE_SECRET_KEY
  
ai:
  enabled: false
  model: "claude-haiku-4-5-20251001"
  api_key: ""                  # or env ANTHROPIC_API_KEY
  
# Global properties added to ALL events
global_properties:
  - name: "screen_name"
    type: "string"
    description: "Screen where event occurred"
  - name: "platform"
    type: "string"
    enum: ["ios", "android", "web"]
  - name: "app_version"
    type: "string"
    
# Custom property rules per event pattern
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
  - match: "*_viewed"
    add:
      - name: "time_on_screen_ms"
        type: "number"
```

---

## CLI usage

```bash
# Basic: extract taxonomy from Figma file
figma-taxonomy extract https://figma.com/file/ABC123/MyApp

# With AI enrichment
figma-taxonomy extract https://figma.com/file/ABC123/MyApp --ai

# Custom config
figma-taxonomy extract https://figma.com/file/ABC123/MyApp -c ./my-config.yaml

# Specific page only
figma-taxonomy extract https://figma.com/file/ABC123/MyApp --page "Onboarding"

# Push directly to Amplitude (Enterprise)
figma-taxonomy push ./output/taxonomy.json

# Validate existing taxonomy against Figma (drift detection)
figma-taxonomy validate ./output/taxonomy.json --figma https://figma.com/file/ABC123/MyApp

# Diff: compare two taxonomy versions
figma-taxonomy diff ./v1/taxonomy.json ./v2/taxonomy.json
```

---

## Development

```bash
# Setup
git clone https://github.com/arcbaslow/figma-taxonomy-gen
cd figma-taxonomy-gen
uv sync

# Set tokens
export FIGMA_TOKEN="your-figma-pat"
export ANTHROPIC_API_KEY="your-key"       # optional, for --ai
export AMPLITUDE_API_KEY="your-key"       # optional, for push
export AMPLITUDE_SECRET_KEY="your-secret" # optional, for push

# Run tests
uv run pytest

# Run CLI
uv run figma-taxonomy extract https://figma.com/file/...

# Run MCP server (for Claude Desktop)
uv run python -m mcp.server
```

---

## Milestones

### v0.1 - Core extraction (week 1-2)
- [ ] Figma API client with caching
- [ ] Node tree walker with interactive element detection
- [ ] Basic naming convention engine (snake_case, {screen}_{element}_{action})
- [ ] JSON output
- [ ] CLI with `extract` command
- [ ] 3 test fixtures: banking, ecommerce, SaaS
- [ ] README with usage examples

### v0.2 - Output formats + config (week 3)
- [ ] Amplitude CSV export
- [ ] Markdown tracking plan export
- [ ] Full `taxonomy.config.yaml` support
- [ ] Global properties and property rules
- [ ] `validate` command (taxonomy vs Figma drift)

### v0.3 - AI enrichment (week 4)
- [ ] Claude integration for property inference
- [ ] Batch screen processing
- [ ] Cost estimation before AI call
- [ ] Interactive review mode (approve/reject suggestions)

### v0.4 - MCP + Amplitude push (week 5-6)
- [ ] MCP server with 4 tools
- [ ] Amplitude Taxonomy API integration (Enterprise)
- [ ] `diff` command
- [ ] `push` command

### v1.0 - Polish (week 7-8)
- [ ] Figma plugin companion (optional, FigJam widget)
- [ ] CI integration (GitHub Action for taxonomy drift detection)
- [ ] Documentation site
- [ ] PyPI publish

---

## Competitive landscape

| Tool | What it does | Gap this tool fills |
|------|-------------|---------------------|
| Amplitude Event Planner (Figma plugin) | Manual label placement on designs, CSV export | No auto-extraction. Manual work per element. |
| Tracking Plan Companion (Glazed) | AI suggestions from uploaded designs | Proprietary SaaS, no CLI, no Amplitude integration, no config |
| Avo | Full tracking plan lifecycle management | Heavy SaaS product ($$$). No Figma extraction. Requires manual plan creation. |
| Iteratively (now Amplitude) | Type-safe tracking code generation | Requires existing tracking plan. Doesn't generate from design. |
| This tool | Auto-extract from Figma -> opinionated taxonomy -> multi-format output | Fills the "design to initial tracking plan" gap. Open source. CLI-first. Configurable. |

---

## Non-goals (for now)

- Not a Figma plugin (REST API + CLI is simpler, more automatable)
- Not a full tracking plan lifecycle tool (Avo does this well)
- Not a code generator (Ampli CLI / Iteratively handles this)
- Not a real-time sync (webhook-based file watching is v2+)
- Does not handle tracking plan versioning/branching (git does this)

---

## Code conventions

- Python 3.11+, type hints everywhere
- Async where beneficial (Figma API calls)
- No classes where functions suffice
- Config is always a dataclass, never raw dict
- All Figma node IDs preserved in output for traceability
- Tests use fixture files, not live API calls
- Error messages are actionable ("Node 1:234 has no text content - using component name 'Button/Primary' instead")
