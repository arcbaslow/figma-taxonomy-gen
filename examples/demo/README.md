# Offline documentation example

These outputs use the synthetic `tests/fixtures/banking_app.json` fixture and contain
no real account, customer or design data. Reproduce them from the repository root:

```bash
uv run figma-taxonomy extract --fixture tests/fixtures/banking_app.json --output examples/demo
```

The CSV is a review file with primary and complete source node ID columns, not
the current Amplitude Data import template. The fixture produces 18 controls in
21 events; the shared login event contains both default and dark button IDs.

`assets/screenshot.png` is an earlier browser capture of generated Markdown in a
documentation viewer, not a live account audit. The files here include the latest
source-list fields.
