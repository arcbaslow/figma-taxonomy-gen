# CLI reference

Excel's `Events` and `Parameters` sheets retain the existing summary layout.
The additional `Event Properties` sheet contains every property association,
including globals and properties beyond the four-column-pair overview, with
types, JSON enum values and all Figma source IDs. All design text is stored as
literal text cells. Text exceeding Excel's cell limit or containing unsupported
control characters fails before replacing an existing workbook; use JSON to
retain such content. CSV retains raw text, while XLSX specifies cell types.

Figma extraction uses `--cache-ttl 300` seconds; validation defaults to
`--cache-ttl 0` so CI checks fetch fresh data. A cache miss makes one file request.
`--offline` uses any valid indexed cache without a token or requests and fails
if none exists. It cannot be combined with `--no-cache`, which disables both
cache reads and writes. Cache age is local freshness, not proof of remote version
equality. Failed online requests never fall back silently to stale data. Older
unindexed caches are refreshed once. No metadata scope is required.

GET requests retry transport failures, 429, and 500/502/503/504 at most twice,
with at most ten seconds of retry sleep. A longer `Retry-After` is reported
without sleeping or retrying early. Other errors fail immediately. Requests
have a 60-second HTTP timeout. See [Figma's retry contract](https://developers.figma.com/docs/rest-api/rate-limits/).

`validate` and `diff` report property schema changes separately from property-name
additions/removals. Type, description and enum membership changes cause
`--exit-code` to return 1. Enum order/duplicates do not count as changes. File diffs
also retain extra stored constraints; validation against Figma reports constraints
the generated schema no longer contains. Renamed events retain schema comparisons.

All commands are subcommands of `figma-taxonomy`. Run any command with `--help` for the
full option list.

## `extract`

Extracts a taxonomy from a Figma file or local fixture and writes it to disk.

```bash
figma-taxonomy extract <figma-url> [OPTIONS]
figma-taxonomy extract --fixture <path> [OPTIONS]
```

| Option             | Default            | Description                                      |
|--------------------|--------------------|--------------------------------------------------|
| `--fixture PATH`   |                    | Read a local Figma JSON dump instead of the API  |
| `-c, --config PATH`|                    | Path to a custom `taxonomy.config.yaml`          |
| `-o, --output DIR` | `./output`         | Directory for generated files                    |
| `-f, --format`     | `output.formats` from config | Comma-separated format list            |
| `--page NAME`      |                    | Limit extraction to one Figma page               |
| `--no-cache`       | `false`            | Disable design-cache reads and writes          |
| `--ai`             | `false`            | Enrich events with Claude-suggested properties   |
| `-y, --yes`        | `false`            | Skip AI cost-estimate confirmation prompt        |

Examples:

```bash
# Only extract the Onboarding page
figma-taxonomy extract https://figma.com/design/ABC/App --page "Onboarding"

# Just produce the JSON artifact for CI
figma-taxonomy extract https://figma.com/design/ABC/App -f json

# Re-run with a fresh API fetch
figma-taxonomy extract https://figma.com/design/ABC/App --no-cache
```

## `validate`

Diffs a stored taxonomy JSON against the current Figma file. Matches events by
the `source` value (`figma:node_id:...`), so renames are reported as renames rather than add+remove.

```bash
figma-taxonomy validate <taxonomy.json> --figma <url>  [OPTIONS]
figma-taxonomy validate <taxonomy.json> --fixture <path> [OPTIONS]
```

| Option             | Default | Description                                   |
|--------------------|---------|-----------------------------------------------|
| `--figma URL`      |         | Figma file URL to validate against            |
| `--fixture PATH`   |         | Local Figma JSON (alternative to `--figma`)   |
| `-c, --config PATH`|         | Path to a custom `taxonomy.config.yaml`       |
| `--no-cache`       | `false` | Skip the Figma API cache                      |
| `--exit-code`      | `false` | Exit non-zero when drift is detected (for CI) |

Reports four categories:

- **Added** — interactive elements in Figma with no matching event in the JSON
- **Removed** — events in the JSON whose node no longer exists in Figma
- **Renamed** — same node, different event name
- **Property changes** — added or removed properties on an existing event

## `diff`

Compares two stored taxonomy JSON files against each other. Same matching strategy
as `validate`.

```bash
figma-taxonomy diff <old.json> <new.json> [--exit-code]
```

Useful for reviewing changes in a PR before they hit the Figma file, or comparing
two branches' tracking plans.

## `push`

Pushes events, categories, and properties to Amplitude's Taxonomy API
(project API access required).

```bash
figma-taxonomy push <taxonomy.json> [OPTIONS]
```

| Option             | Default                    | Description                             |
|--------------------|----------------------------|-----------------------------------------|
| `--dry-run`        | `false`                    | Preview local input without API requests or credentials |
| `--base-url URL`   | `https://amplitude.com`    | Override the API host (EU, self-hosted) |

Reads `AMPLITUDE_API_KEY` and `AMPLITUDE_SECRET_KEY` from env. Existing events are
GET'd first and skipped on conflict. See [Amplitude push](amplitude.md) for details.

## `figma-taxonomy-mcp`

Separate console script. Runs the MCP server over stdio for Claude Desktop /
claude.ai integration. Takes no arguments. See [MCP server](mcp.md).
