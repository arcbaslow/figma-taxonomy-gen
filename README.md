# figma-taxonomy-gen

Generate an [Amplitude](https://amplitude.com) event taxonomy straight from a Figma file.

**Docs:** [arcbaslow.github.io/figma-taxonomy-gen](https://arcbaslow.github.io/figma-taxonomy-gen/)

## Why

Most tracking plans start the same way: someone reads through Figma, writes a spreadsheet by hand, and the spreadsheet goes stale a week later.

This tool skips that first manual pass. It pulls the interactive parts out of a design file, turns them into event names and properties, and writes the outputs teams usually want to review or import.

## What it does

```
Figma file → extract interactive elements → apply naming rules → write outputs
```

1. Read a Figma file through the REST API, or load a local JSON fixture.
2. Keep the parts that matter for analytics: buttons, inputs, toggles, tabs, cards, modals, and similar UI.
3. Group those elements into screens based on page and frame structure.
4. Build event names from a configurable pattern. The default is `{screen}_{element}_{action}`.
5. Add properties from simple rules. For example, every `*_fail` event can get `error_description`.
6. Write the result as Excel, Amplitude CSV, JSON, or Markdown.

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

By default the command writes four files to `./output/`:

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

Once `taxonomy.json` is in your repo, `validate` compares it against the current Figma file. Events are matched by Figma `node_id`, so a renamed component shows up as a rename instead of a fake add/remove pair. The report covers:

- **Added**: elements that exist in Figma but not in the stored taxonomy
- **Removed**: events in the taxonomy that no longer map to any Figma node
- **Renamed**: same node, different event name
- **Property changes**: properties added or removed on an existing event

Add `--exit-code` to fail CI when the design and the tracking plan disagree.

## AI enrichment (optional)

With `--ai`, the tool sends one prompt per flow to an Anthropic model and merges the suggested properties back into the generated events. This helps with things the rule engine cannot infer cleanly on its own, like enum values from variants, contextual IDs, or state flags.

```bash
uv pip install 'figma-taxonomy-gen[ai]'
export ANTHROPIC_API_KEY="sk-ant-..."
figma-taxonomy extract --fixture tests/fixtures/banking_app.json --ai
```

Before calling the API, the CLI prints a cost estimate and asks for confirmation. Use `--yes` to skip that prompt in scripts. Haiku is the default; set `ai.model` in the config if you want Sonnet for screens with a lot of variants.

The banking-app fixture (6 flows, Haiku) costs about $0.001. A real 30-50 screen fintech app usually lands somewhere between $0.01 and $0.10.

## MCP server

The package also ships with an MCP server, so you can call the extractor from any MCP-compatible client. It exposes three tools:

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

Useful when you want to review taxonomy changes in a pull request before pushing anything to Amplitude.

## CI drift check

The repo includes a composite action that fails a pull request when the Figma design and the committed taxonomy no longer match. Drop this into `.github/workflows/taxonomy-drift.yml`:

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

The job exits non-zero and prints a readable diff when events are added, removed, renamed, or their properties change.

## Configuration

Add a `taxonomy.config.yaml` to change naming rules and output defaults:

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

See [`taxonomy.config.yaml`](taxonomy.config.yaml) for the full set of options and defaults.

## How element detection works

The extractor decides whether a node is interactive in three ways:

1. **Name patterns**: matches component names against known patterns (`button`, `input`, `toggle`, `dropdown`, etc.).
2. **Prototype interactions**: any node with a Figma interaction (click, hover, drag) counts as interactive.
3. **Component types**: only `COMPONENT`, `COMPONENT_SET`, and `INSTANCE` nodes are considered.

It skips icons, dividers, loaders, and other decorative placeholders.

## Naming convention

Events follow the pattern `{screen}_{element}_{action}`:

| Figma structure | Generated event |
|----------------|----------------|
| Page "Login" → Frame "01 - Login Screen" → Button "Log In" | `login_screen_log_in_clicked` |
| Page "Home" → Frame "Home - Default" → Tab "Accounts" | `home_accounts_viewed` |
| Page "Payments" → Frame "Payment Form" → Input "Amount" | `payment_form_amount_entered` |

Screen names are cleaned before event generation: numbered prefixes are stripped and common variant suffixes are collapsed.

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

## License

MIT
