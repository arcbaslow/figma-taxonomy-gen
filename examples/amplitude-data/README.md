# Offline Amplitude Data example

Generated from synthetic variant controls; no account or design credentials:

```bash
uv run figma-taxonomy extract --fixture tests/fixtures/variant_sources.json --format amplitude-csv --output examples/amplitude-data
```

`taxonomy.amplitude.csv` targets the published Amplitude Data import schema.
`taxonomy.amplitude.json` preserves the complete control/frame IDs and property
schemas for local validation. Only the CSV is an import file. This example has
not been imported into a real project; see the [import guide](../../docs/amplitude.md)
for supported schemas and the effects of importing blank metadata fields.
