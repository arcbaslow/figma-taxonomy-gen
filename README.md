# figma-taxonomy-gen

CLI that pulls interactive elements out of a Figma file and generates an [Amplitude](https://amplitude.com) event taxonomy.

**Docs:** [arcbaslow.github.io/figma-taxonomy-gen](https://arcbaslow.github.io/figma-taxonomy-gen/)

## Why

Tracking plans usually live in a spreadsheet that the PM wrote by hand after staring at Figma for an afternoon. Then the spreadsheet drifts. This tool generates the first version of that spreadsheet straight from the design file, so at least the starting point stays in sync.

## What it does

```
Figma file → extract interactive elements → apply naming rules → write outputs
```

1. Reads the Figma file via the REST API (or a local JSON fixture).
2. Walks the node tree and keeps the interactive bits: buttons, inputs, toggles, tabs, cards, modals, etc.
3. Groups elements by page/frame into screens.
4. Generates event names from a configurable pattern (default `{screen}_{element}_{action}`).
5. Applies property rules (e.g. every `*_fail` event gets `error_description`).
6. Writes Excel, Amplitude CSV, JSON Schema, and Markdown.

## Install

```bash
# uv
uv pip install figma-taxonomy-gen

# pip
pip install figma-taxonomy-gen
```

From source:

```bash
git clone https://github.com/arcbaslow/figma-taxonomy-gen
cd figma-taxonomy-gen
uv sync
```

## Quick start

From a real Figma file:

```bash
export FIGMA_TOKEN="your-figma-personal-access-token"
figma-taxonomy extract https://figma.com/file/ABC123/MyApp
```

From a fixture, if you want to try it without a token:

```bash
figma-taxonomy extract --fixture tests/fixtures/banking_app.json
```

Four files land in `./output/`:

| File | Format | What it's for |
|------|--------|---------------|
| `taxonomy.xlsx` | Excel | Team review, matches common tracking-plan templates |
| `taxonomy.csv` | Amplitude CSV | Direct import into Amplitude Data |
| `taxonomy.json` | JSON Schema | Validation, CI/CD, custom tooling |
| `taxonomy.md` | Markdown | PR review, wiki, docs |

## CLI

```bash
# Basic extraction
figma-taxonomy extract https://figma.com/file/ABC123/MyApp

# Custom output directory
figma-taxonomy extract https://figma.com/file/ABC123/MyApp --output ./my-output

# Specific formats only
figma-taxonomy extract ... --format excel,csv

# One page
figma-taxonomy extract ... --page "Onboarding"

# Custom config
figma-taxonomy extract ... --config ./my-config.yaml

# Skip API cache
figma-taxonomy extract ... --no-cache

# Check whether a stored taxonomy still matches the current Figma file
figma-taxonomy validate ./output/taxonomy.json --figma https://figma.com/file/ABC123/MyApp

# CI mode: validate against a fixture, exit non-zero if anything drifted
figma-taxonomy validate ./output/taxonomy.json --fixture ./figma.json --exit-code
```

## Drift detection

Once `taxonomy.json` is committed to your repo, `validate` compares it against the current Figma file. Events are matched by Figma `node_id`, so a renamed component shows up as a rename instead of an add plus a remove. The report covers:

- **Added**: elements that exist in Figma but not in the stored taxonomy
- **Removed**: events in the taxonomy that no longer map to any Figma node
- **Renamed**: same node, different event name
- **Property changes**: properties added or removed on an existing event

Add `--exit-code` to fail CI when the design and the tracking plan disagree.

## AI enrichment (optional)

With `--ai`, the tool sends one prompt per flow to an Anthropic model and merges the suggested properties into the generated events. Useful for things the rule engine can't guess: enum values from component variants, contextual IDs, state flags.

```bash
uv pip install 'figma-taxonomy-gen[ai]'
export ANTHROPIC_API_KEY="sk-ant-..."
figma-taxonomy extract --fixture tests/fixtures/banking_app.json --ai
```

Before calling the API, the CLI prints an estimated cost and asks you to confirm. Pass `--yes` to skip the prompt in scripts. Haiku is the default; set `ai.model` in the config to use Sonnet for screens with a lot of variants.

The banking-app fixture (6 flows, Haiku) costs about $0.001. A real 30–50 screen fintech app usually runs $0.01 to $0.10.

## MCP server

The package ships an MCP server so any MCP-compatible client can call the tool directly. Three tools are exposed:

| Tool | Description |
|------|-------------|
| `extract_taxonomy` | Extract a taxonomy from a Figma file or local fixture |
| `validate_taxonomy` | Diff a stored taxonomy JSON against the current Figma file |
| `export_taxonomy` | Write a taxonomy to disk as json / csv / markdown / excel |

Install and run:

```bash
uv pip install 'figma-taxonomy-gen[mcp]'
figma-taxonomy-mcp
```

Example MCP client config:

```json
{
  "mcpServers": {
    "figma-taxonomy": {
      "command": "figma-taxonomy-mcp",
      "env": { "FIGMA_TOKEN": "your-figma-pat" }
    }
  }
}
```

## Push to Amplitude (Enterprise)

If your Amplitude plan gives you access to the Taxonomy API:

```bash
export AMPLITUDE_API_KEY="..."
export AMPLITUDE_SECRET_KEY="..."
figma-taxonomy push ./output/taxonomy.json            # real push
figma-taxonomy push ./output/taxonomy.json --dry-run  # preview only
```

## Diff two taxonomy files

```bash
figma-taxonomy diff ./v1/taxonomy.json ./v2/taxonomy.json --exit-code
```

Handy for reviewing taxonomy changes in a PR before they go to Amplitude.

## CI drift check

There's a composite action in the repo for failing pull requests when the Figma design and the committed taxonomy disagree. Drop this in `.github/workflows/taxonomy-drift.yml`:

```yaml
name: Taxonomy drift check
on:
  pull_request:
    paths:
      - "tracking/taxonomy.json"

jobs:
  drift:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: arcbaslow/figma-taxonomy-gen/.github/actions/drift-check@v0.4.0
        with:
          taxonomy-path: tracking/taxonomy.json
          figma-url: https://figma.com/design/ABC123/MyApp
          figma-token: ${{ secrets.FIGMA_TOKEN }}
```

The job exits non-zero with a readable diff when events are added, removed, renamed, or their properties change.

## Configuration

Drop a `taxonomy.config.yaml` in your project to tweak naming:

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

See [`taxonomy.config.yaml`](taxonomy.config.yaml) for every option with its default.

## How element detection works

The tool identifies interactive elements in three ways:

1. **Name patterns**: matches component names against known patterns (`button`, `input`, `toggle`, `dropdown`, etc.).
2. **Prototype interactions**: any node with a Figma interaction (click, hover, drag) counts as interactive.
3. **Component types**: only `COMPONENT`, `COMPONENT_SET`, and `INSTANCE` nodes are considered.

Icons, dividers, loaders, and placeholders are filtered out.

## Naming convention

Events follow the pattern `{screen}_{element}_{action}`:

| Figma structure | Generated event |
|----------------|----------------|
| Page "Login" → Frame "01 - Login Screen" → Button "Log In" | `login_screen_log_in_clicked` |
| Page "Home" → Frame "Home - Default" → Tab "Accounts" | `home_accounts_viewed` |
| Page "Payments" → Frame "Payment Form" → Input "Amount" | `payment_form_amount_entered` |

Screen names are cleaned on the way in: numbered prefixes stripped, variant suffixes collapsed.

## Property rules

You can attach properties to events by name pattern:

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

Global properties like `screen_name` and `platform` are attached to every event.

## Development

```bash
git clone https://github.com/arcbaslow/figma-taxonomy-gen
cd figma-taxonomy-gen
uv sync

# Tests
uv run pytest -v

# CLI
uv run figma-taxonomy extract --fixture tests/fixtures/banking_app.json
```

## Roadmap

- [x] **v0.1**: Core extraction pipeline, CLI, 4 output formats
- [x] **v0.2**: Full config support, `validate` command (taxonomy drift detection)
- [x] **v0.3**: AI enrichment via Anthropic models (property inference from screen context)
- [x] **v0.4**: MCP server support, Amplitude API push, `diff` command
- [x] **v1.0**: CI workflows, drop-in drift-check action, MkDocs site, PyPI publish (ready to tag)

## License

MIT
