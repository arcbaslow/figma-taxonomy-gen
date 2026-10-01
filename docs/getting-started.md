# Getting started

For online Figma access, set `FIGMA_TOKEN` and optionally `FIGMA_TOKEN_TYPE`:
`pat` (default), `plan`, or `oauth`. PAT and REST API plan tokens use
`X-Figma-Token`; OAuth access tokens use `Authorization: Bearer`. The file
endpoint requires `file_content:read`. Plan tokens must allow access to the
selected resource and must be REST API tokens, not Figma CLI tokens.
See [plan tokens](https://developers.figma.com/docs/rest-api/plan-access-tokens/)
and [OAuth access tokens](https://developers.figma.com/docs/rest-api/oauth-apps/).

Credentials are read from the environment, never saved in config or cache. OAuth
app registration, consent, token exchange and refresh remain the caller's
responsibility; this local tool accepts an already-issued access token. Offline
fixtures and explicit offline cache use require no credentials. Header selection
is mock-tested; account permissions and token refresh have not been tested live.

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

Use `--no-cache` to disable both reads and writes of the design cache. Branch URLs
fetch the branch rather than its parent file. Access failures report the required
scope and file-access checks; rate-limit failures report `Retry-After`.
See the [current Figma quotas](https://developers.figma.com/docs/rest-api/rate-limits/)
for your seat and file plan.

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
| `taxonomy.csv`  | Event/property review rows with source node IDs |
| `taxonomy.json` | Canonical, validation, CI/CD                   |
| `taxonomy.md`   | PR reviews, wiki, documentation                |

CSV contains `Source Node ID` and `Source Node IDs`; Excel uses columns N and O.
The plural column is a JSON array. Pageview sources are screen frame IDs, including
empty screens and variants. The review format is not a direct import file.
Use `--format amplitude-csv` for the separate Amplitude Data profile and its
JSON provenance companion; see [the import guide](amplitude.md#amplitude-data-csv-import).

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
- [Push](amplitude.md) events to Amplitude with project Taxonomy API access
- Wire up the [drift-check action](ci.md) on your app repo
