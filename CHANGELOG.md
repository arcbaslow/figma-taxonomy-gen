# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning is [semantic](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - 2026-08-14
### Added

- `CONTRIBUTING.md`, `SECURITY.md`, issue and pull-request templates,
  Dependabot config.
- Ruff lint step in CI, with the rule set pinned explicitly in
  `pyproject.toml`. Ruff's implicit default changes between releases,
  which would otherwise turn an unrelated upgrade into a red CI run.
- README badges and this changelog.

## [0.4.0] - 2026-04-28

### Added

- MCP server (`figma-taxonomy-mcp`) exposing four tools:
  `extract_taxonomy`, `suggest_events`, `validate_taxonomy`,
  `export_taxonomy`. Ships with `pip install figma-taxonomy-gen[mcp]`.
- Amplitude Taxonomy API push for Enterprise accounts
  (`figma-taxonomy push`).
- `diff` command comparing two taxonomy versions.
- MkDocs documentation site deployed to GitHub Pages.
- Reusable `drift-check` composite action for CI taxonomy drift
  detection.

## [0.3.0]

### Added

- AI property inference via the Anthropic SDK (`--ai`). Batches screen
  context, infers property names, types, enum values from component
  variants, and category assignments.
- Cost estimation before the AI call.

## [0.2.0]

### Added

- Amplitude CSV export in Amplitude Data import format.
- Markdown tracking-plan export.
- Excel output matching the tracking-plan template.
- Full `taxonomy.config.yaml` support: global properties and
  per-pattern property rules.
- `validate` command for taxonomy-versus-Figma drift detection.

## [0.1.0]

### Added

- Figma REST API client with file-version-keyed local caching.
- Node tree walker with interactive-element detection: name-pattern
  heuristics, prototype-interaction detection, and exclude patterns.
- Screen map built from the frame hierarchy, with variant-frame
  collapsing.
- Naming convention engine, `{screen}_{element}_{action}` by default,
  configurable style and action verbs.
- JSON Schema output with Figma node IDs preserved for traceability.
- `extract` CLI command.

[Unreleased]: https://github.com/arcbaslow/figma-taxonomy-gen/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/arcbaslow/figma-taxonomy-gen/releases/tag/v0.4.0
