# Getting started

## Install

=== "uv (recommended)"

    ```bash
    uv pip install figma-taxonomy-gen
    ```

=== "pip"

    ```bash
    pip install figma-taxonomy-gen
    ```

=== "From source"

    ```bash
    git clone https://github.com/arcbaslow/figma-taxonomy-gen
    cd figma-taxonomy-gen
    uv sync --extra dev
    ```

Optional extras:

| Extra  | Adds              | Needed for                   |
|--------|-------------------|------------------------------|
| `ai`   | `anthropic` SDK   | `--ai` enrichment flag       |
| `mcp`  | `mcp` SDK         | `figma-taxonomy-mcp` server  |
| `docs` | `mkdocs-material` | Building these docs locally  |

Install multiple at once:

```bash
uv pip install 'figma-taxonomy-gen[ai,mcp]'
```

## Get a Figma token

1. Figma → your avatar → **Settings** → **Security** → **Personal access tokens**
2. Click **Generate new token**, give it **File content: Read** scope
3. Export it:

    ```bash
    export FIGMA_TOKEN="figd_..."
    ```

The token is read from the `FIGMA_TOKEN` environment variable on every API call.
It's never logged or written to disk.

## First extraction

Point it at a real Figma file:

```bash
figma-taxonomy extract https://figma.com/design/ABC123/MyApp
```

…or run against the bundled banking-app fixture (no token needed):

```bash
figma-taxonomy extract --fixture tests/fixtures/banking_app.json
```

Either produces four files in `./output/`:

| File            | Purpose                                        |
|-----------------|------------------------------------------------|
| `taxonomy.xlsx` | Team review; matches common tracking templates |
| `taxonomy.csv`  | Direct import into Amplitude Data              |
| `taxonomy.json` | Canonical, validation, CI/CD                   |
| `taxonomy.md`   | PR reviews, wiki, documentation                |

## Commit the JSON

The `taxonomy.json` is the canonical artifact. Commit it to the app repo:

```bash
cp output/taxonomy.json tracking/taxonomy.json
git add tracking/taxonomy.json
git commit -m "Add initial tracking plan"
```

From here you can:

- Run [`validate`](cli-reference.md#validate) in CI to catch drift between the JSON and the current Figma design
- Use [`diff`](cli-reference.md#diff) to review taxonomy changes in PRs
- [Push](amplitude.md) events to Amplitude via the Taxonomy API (Enterprise)
- Wire up the [drift-check action](ci.md) on your app repo
