## What this changes

<!-- One sentence on what changed and why. -->

## How to verify

<!--
uv run ruff check src/ tests/
uv run pytest -v

Add manual smoke-test steps if relevant.
-->

## Checklist

- [ ] `uv run ruff check src/ tests/` clean
- [ ] `uv run pytest -v` passes
- [ ] New behaviour is covered by a fixture, not a live API call
- [ ] No Figma / Anthropic / Amplitude tokens in committed files
- [ ] Figma node IDs still preserved in output
- [ ] Naming behaviour stayed configurable rather than hardcoded
- [ ] CHANGELOG.md updated if this is user-visible
- [ ] `docs/` updated if the user-facing surface changed
