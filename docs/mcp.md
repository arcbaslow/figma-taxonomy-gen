# MCP server

The optional dependency targets `mcp>=2.2,<3`, locked at 2.2.0. An offline stdio integration test
starts the real server process, negotiates a session, lists tools, extracts a
fixture, exports JSON, validates it, detects schema drift and checks tool errors.

The server uses `MCPServer` and explicitly selects stdio, following the
[upstream migration guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md).
Protocol tests use the SDK's snake_case model fields; tool names, arguments and
JSON payloads are unchanged. MCP brings its own `httpx2` dependency; the Figma and
Amplitude clients continue using their separately declared `httpx` dependency.
Upgrade an existing checkout with `uv sync --extra mcp` (plus any other needed
extras), or reinstall `figma-taxonomy-gen[mcp]` from the updated source. Python
3.11 remains supported. No remote MCP service was contacted during verification.

Extraction and validation accept `cache_ttl`, `offline`, and `no_cache`.
Extraction defaults to 300 seconds of cache reuse; validation defaults to zero
for fresh remote data. Offline mode requires an existing indexed cache, makes no
requests and needs no token. Fixture paths remain offline independently of these
options. `offline` and `no_cache` cannot be combined for API sources.

Extraction also accepts `explain: true` (default false), adding an `explanation`
object with versioned node decisions and generated event names. The event payload
is unchanged. See [detection reports](detection.md#when-detection-goes-wrong).

The tool ships an [MCP](https://modelcontextprotocol.io) server so Claude Desktop
and claude.ai can call its functions directly, without shelling out to the CLI.

## Install and run

```bash
uv pip install 'figma-taxonomy-gen[mcp]'
```

The installer adds a console script `figma-taxonomy-mcp` that runs the server over
stdio:

```bash
figma-taxonomy-mcp
```

You won't normally run this manually — Claude Desktop launches it for you.

## Claude Desktop configuration

Edit `claude_desktop_config.json`:

=== "macOS"

    `~/Library/Application Support/Claude/claude_desktop_config.json`

=== "Windows"

    `%APPDATA%\Claude\claude_desktop_config.json`

=== "Linux"

    `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "figma-taxonomy": {
      "command": "figma-taxonomy-mcp",
      "env": {
        "FIGMA_TOKEN": "figd_your_token_here"
      }
    }
  }
}
```

Restart Claude Desktop. You should see `figma-taxonomy` listed in the tool picker.

## Exposed tools

### `extract_taxonomy`

Extract a taxonomy from a Figma file or local fixture.

| Argument               | Type           | Description                                       |
|------------------------|----------------|---------------------------------------------------|
| `figma_url_or_path`    | `str`          | Figma URL, file key, or local fixture path        |
| `config_path` (opt.)   | `str \| null`  | Path to a custom `taxonomy.config.yaml`           |
| `page` (opt.)          | `str \| null`  | Limit to a single Figma page                      |

Returns: `{"count": int, "events": [...]}` with every event's name, category,
description, properties, legacy primary `source_node_id`, and all contributing
`source_node_ids`. Shared event names within a page retain every contributing
control ID. Pageviews carry screen frame IDs and include screens with no controls.
Use `{page}` in the configured naming pattern to distinguish matching screen names
on different pages. Cross-page event-name collisions raise an actionable error.

Pass that entire result directly to `export_taxonomy` or `validate_taxonomy`.
Both accept either this extraction list or the stored JSON event map. JSON export
normalizes to the stored map, retaining source IDs, property descriptions and enums.
Explicit page selection overrides exclusions; a missing page raises an error
listing available pages, matching CLI behavior.

MCP 1.x installations must upgrade the optional dependency with this source
version. External clients still use standard MCP JSON-RPC; Python SDK users
should follow the upstream migration guide when inspecting protocol objects.

### `validate_taxonomy`

Diff a stored taxonomy against the current Figma file.

| Argument               | Type           | Description                                       |
|------------------------|----------------|---------------------------------------------------|
| `taxonomy_json`        | `dict`         | Parsed taxonomy JSON (must contain `events` key)  |
| `figma_url_or_path`    | `str`          | Figma URL or path to local fixture                |
| `config_path` (opt.)   | `str \| null`  | Path to a custom `taxonomy.config.yaml`           |

Returns: `{"is_clean": bool, "added": [...], "removed": [...], "renamed": [...],
"property_changes": [...], "source_changes": [...], "category_changes": [...]}`.
Category changes include `event_name`, `from`, and `to` flow names and make
`is_clean` false. Each source change includes
`event_name`, `added`, and `removed` node-ID lists. Any source membership change
makes `is_clean` false; reordering sources does not. Older single-source inputs
remain valid, but newly discovered variant sources are reported as additions.

### `export_taxonomy`

Write a taxonomy to disk in a specific format.

| Argument               | Type           | Description                                       |
|------------------------|----------------|---------------------------------------------------|
| `taxonomy_json`        | `dict`         | Parsed taxonomy JSON                              |
| `format`               | `str`          | `json`, `csv`, `markdown`, `excel`, or `amplitude-csv` |
| `output_path`          | `str`          | Destination file path                             |

Returns: `{"output_path": str, "format": str}`.

For `amplitude-csv`, the path must end in `.csv`; a sibling `.json` companion is
always written to preserve sources and schemas. The result additionally includes
`companion_path` and `notes` about import behavior. Both stored event maps and
extraction results are supported. Unsupported schemas fail before output writes.
The `csv` format remains the review CSV. See [Amplitude import](amplitude.md#amplitude-data-csv-import).

## Example conversations

In Claude Desktop, you can now say things like:

> "Extract the taxonomy from this Figma file and show me the event names grouped by
> flow: `https://figma.com/design/ABC123/MyApp`"

> "Compare my committed `tracking/taxonomy.json` to the current state of that Figma
> file — what drifted?"

> "Take this extraction result and export it as an Amplitude CSV."

Claude calls the tools, gets structured data back, and can do further analysis on
top (grouping, renaming suggestions, stakeholder summaries) without the tool
needing to know about any of that.
