# Offline documentation example

These outputs use the synthetic `tests/fixtures/banking_app.json` fixture and contain
no real account, customer or design data. Reproduce them from the repository root:

```bash
uv run figma-taxonomy extract --fixture tests/fixtures/banking_app.json --output examples/demo
```

The CSV is a review file with source node IDs, not the current Amplitude Data
import template.

`assets/screenshot.png` is a browser capture of the generated Markdown in a
documentation viewer, not a live account audit.
