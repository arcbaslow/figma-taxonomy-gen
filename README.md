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

# Detect drift between a stored taxonomy and the current Figma file
figma-taxonomy validate ./output/taxonomy.json --figma https://figma.com/file/ABC123/MyApp

# Validate against a fixture; exit non-zero if drift detected (for CI)
figma-taxonomy validate ./output/taxonomy.json --fixture ./figma.json --exit-code
```

## Drift detection

Once you've committed a `taxonomy.json` to your repo, run `validate` to check whether the
design has changed since. It matches events by Figma `node_id` (so renames are detected as
renames, not add+remove), and reports:

- **Added** — interactive elements that exist in Figma but not in the stored taxonomy
- **Removed** — events in the stored taxonomy that no longer correspond to any Figma node
- **Renamed** — same node, different event name (e.g., after a component was renamed)
- **Property changes** — properties added or removed on an existing event

Wire this into CI with `--exit-code` to fail the build when designs and the tracking plan
drift apart.

## AI enrichment (optional)

With `--ai`, the tool sends one prompt per flow to Claude and merges suggested properties
into the generated events. Good for things like enum values derived from component variants,
contextual identifiers, and state flags that rule-based generation can't infer.

```bash
uv pip install 'figma-taxonomy-gen[ai]'
export ANTHROPIC_API_KEY="sk-ant-..."
figma-taxonomy extract --fixture tests/fixtures/banking_app.json --ai
```

Before calling the API, the CLI prints an estimated cost and prompts for confirmation
(use `--yes` to skip the prompt in scripts). Haiku is the default; override via `ai.model`
in the config to use Sonnet for complex screens.

Cost estimate for the banking-app fixture (6 flows, Haiku): ~$0.001. A real 30-50 screen
fintech app typically lands between $0.01 and $0.10.

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
- [x] **v0.2** — Full config support, `validate` command (taxonomy drift detection)
- [x] **v0.3** — AI enrichment via Claude (property inference from screen context)
- [ ] **v0.4** — MCP server for Claude Desktop, Amplitude API push, `diff` command
- [ ] **v1.0** — CI integration, documentation site, PyPI publish

## License

MIT
