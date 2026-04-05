# MCP server

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
description, properties, and source node id.

### `validate_taxonomy`

Diff a stored taxonomy against the current Figma file.

| Argument               | Type           | Description                                       |
|------------------------|----------------|---------------------------------------------------|
| `taxonomy_json`        | `dict`         | Parsed taxonomy JSON (must contain `events` key)  |
| `figma_url_or_path`    | `str`          | Figma URL or path to local fixture                |
| `config_path` (opt.)   | `str \| null`  | Path to a custom `taxonomy.config.yaml`           |

Returns: `{"is_clean": bool, "added": [...], "removed": [...], "renamed": [...],
"property_changes": [...]}`.

### `export_taxonomy`

Write a taxonomy to disk in a specific format.

| Argument               | Type           | Description                                       |
|------------------------|----------------|---------------------------------------------------|
| `taxonomy_json`        | `dict`         | Parsed taxonomy JSON                              |
| `format`               | `str`          | `json`, `csv`, `markdown`, or `excel`             |
| `output_path`          | `str`          | Destination file path                             |

Returns: `{"output_path": str, "format": str}`.

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
