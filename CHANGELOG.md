# Changelog

All notable changes to this project are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning is [semantic](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Add an opt-in `amplitude-csv` profile for CLI/config/MCP with all 33 published Amplitude Data import columns, event-specific properties, string enums and a mandatory JSON provenance companion. Validate unsupported schemas before writing; retain the existing review CSV and default formats.

- Support `{page}` in naming patterns and include all screen frame IDs in pageviews, including empty screens and variants. Report category changes in CLI/MCP drift results.

- Add all contributing Figma node IDs to JSON (`sources`), MCP (`source_node_ids`), Markdown, and CSV/Excel (`Source Node IDs`), while keeping the legacy primary fields. Report source membership changes in CLI/MCP drift checks.

- Discover screen frames inside nested Figma sections while keeping page flow names and source node IDs.

### Changed

- Document the researched roadmap, remaining provenance/configuration limits, actual screen naming and property precedence, and valid composite-action CI examples.

### Fixed

- Write taxonomy JSON explicitly as UTF-8, including import companions; reject duplicate properties in MCP extraction results instead of silently overwriting them.

- Use each control's owning page for its category; reject cross-page event-name collisions and control/pageview collisions instead of silently combining their identities.

- Visit every variant frame and merge identical full event names without discarding nodes or variant-only controls. Reject truncation collisions with actionable errors; match renames through any unambiguous shared source.

- Preserve source node IDs in CSV and Excel review exports. Clarify that the review CSV is not the current Amplitude Data import template.

- Correct Opus 4.6 price estimates, report unknown model prices as unavailable, and count AI-added properties before the in-place merge.

- Accept MCP extraction results directly in export and validation, preserving node IDs and enum schemas; align explicit and missing page handling with the CLI.

- Keep Amplitude dry runs entirely offline, send event categories under the documented API field, and report API-declared failures rather than counting them as successful writes.

- Honor configured naming patterns and snake_case/camelCase styles; apply the configured screen action and event-name length cap to pageviews too.

- Detect named frames, groups, text and rectangles with prototype interactions, preserving their inferred element type and node ID.

- Fetch the selected Figma branch, reject malformed file URLs/keys, explain access and rate-limit errors, and prevent cache reads and writes with `--no-cache`.

## [0.4.2] - 2026-09-08

### Added

- Distinct SVG banner and project icon, linked CI/release badges, and a screenshot of real output generated from synthetic fixtures.
- Reproducible offline examples, release notes, maintainer release instructions and a verification record.

### Changed

- Constrained the MCP extra to SDK 1.x to keep `FastMCP` server construction working on a fresh installation.
- Aligned the package's public `__version__` and local lockfile entry with the release version.
- Reorganized README around installation, first run, example output, supported capabilities and the actual CI checks.
- Corrected installation and capability claims, with explicit distinctions between agent workflows, direct CLI operations and optional integrations.

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

[Unreleased]: https://github.com/arcbaslow/figma-taxonomy-gen/compare/v0.4.2...HEAD
[0.4.0]: https://github.com/arcbaslow/figma-taxonomy-gen/releases/tag/v0.4.0
