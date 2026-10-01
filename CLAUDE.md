# CLAUDE.md

## Project: `figma-taxonomy-gen`

**One-line:** CLI + MCP tool that pulls interactive UI elements out of a Figma file and generates an Amplitude event taxonomy, with optional AI-powered property inference.

---

## Status and asset role (2026-08)

Shipped: v0.4 on PyPI, MkDocs docs site, CI with drift-check. Architecture,
config reference, CLI usage and the original build spec live in `README.md`
and `docs/` - this file keeps only what the repo cannot tell you.

**Mode: maintenance.** Bugfixes, Figma/Amplitude API changes, and docs only.
The active OSS build slot belongs to capi-kit; new features here need an
explicit owner decision.

Role of the asset: flagship proof of competence for the tracking-plan /
taxonomy practice. Its users are implementers, not buyers - the README's job
is to route readers to Good Labs services (taxonomy design, tracking-plan
audit). Keep that link present and current. Planned loop: taxonomy generated
here gets validated against runtime by the Tracking Spy Extension and linted
by tracking-plan-lint (see vault, projects/).

---

## Architecture

The MCP server lives inside the package (`src/figma_taxonomy/mcp_server.py`) rather than
a separate top-level `mcp/` directory, so it ships with `pip install figma-taxonomy-gen[mcp]`
and is exposed as the `figma-taxonomy-mcp` console script declared in `pyproject.toml`.

---

## Key design decisions

### 1. Interactive element detection

Figma nodes don't have a semantic "this is a button" flag. Detection relies on name-pattern and node-property heuristics (see `src/figma_taxonomy/extractor.py` and `docs/detection.md`).

Prototype interactions (including legacy transitions) identify controls regardless
of component type, subject to visibility, exclusions and ancestor traversal.
Ordered name/node overrides make those policies configurable; `--explain` reports
decisions and generated event sources.

### 2. Screen context inference

The tool builds a screen map from the Figma frame hierarchy:

```
Page: "Onboarding"
  Frame: "01 - Welcome"        -> screen: welcome
  Frame: "02 - Phone Input"    -> screen: phone_input
  Frame: "03 - OTP"            -> screen: otp
  Frame: "04 - Success"        -> screen: success

Page: "Home"
  Frame: "Home - Default"      -> screen: home
  Frame: "Home - With Offer"   -> screen: home (variant, not separate screen)
```

Frame naming conventions are configurable. Add `- With Offer` to the suffix list
for that example. Every variant is visited; matching event names within a page
merge their sources. The owning page supplies the category. Use `{page}` in the
naming pattern for page-qualified names; cross-page event-name collisions are
errors. Pageviews preserve frame IDs and include empty screens through the screen
inventory. Python callers should pass `screens=extract_screens(...)` to include
empty frames when calling `generate_taxonomy` directly.

### 3. Naming convention engine

The default `max_event_length: 64` is this project's configurable naming policy,
not a verified universal Amplitude limit. Truncation collisions fail explicitly.

---

## Figma API usage

### Authentication
- Token via `FIGMA_TOKEN`; `FIGMA_TOKEN_TYPE=pat` (default), `plan`, or `oauth`.
- PAT/REST API plan tokens use `X-Figma-Token`; OAuth uses bearer authorization.
  An explicit environment token is never persisted or auto-refreshed. With the
  optional `oauth` extra, `auth login` handles consent/code exchange for the user's
  registered app; access/refresh tokens and app credentials stay in the native
  OS credential store. `FIGMA_TOKEN_TYPE=oauth` with no `FIGMA_TOKEN` selects that
  session and enables refresh. See `docs/oauth.md`; no plaintext fallback.

### Limits
- The client uses the file endpoint once per cache miss; extraction caches have a
  five-minute TTL and validation fetches fresh data by default. Offline cache use
  is explicit. No metadata endpoint or extra scope is required.
- Limits vary by seat and resource plan. GET retries respect `Retry-After`, stop
  after three attempts and allow at most ten seconds of retry waiting.
  [Rate limits](https://developers.figma.com/docs/rest-api/rate-limits/).

---

## Amplitude Taxonomy API integration

The current [Taxonomy API reference](https://amplitude.com/docs/apis/analytics/taxonomy)
describes planned schemas; confirm entitlement for the target project. Push is
create-only and scopes property reads/writes to each event. Matching definitions
are reused; category/description/schema conflicts require manual review. It never
updates shared definitions or restores/deletes events. See `docs/amplitude.md`
for supported types, partial-failure behavior and the separate Data CSV profile.

### Auth
- Basic auth: `{api_key}:{secret_key}` base64-encoded
- Env vars: `AMPLITUDE_API_KEY`, `AMPLITUDE_SECRET_KEY`

---

## AI enrichment (Claude)

When `--ai` is passed or `ai.enabled` is explicitly configured:

1. Batch events within each flow, bounded by event count and prompt size.
2. Send event names, descriptions and existing properties in a JSON-output prompt.
3. Request suggested property names, types, descriptions and optional enums.
4. Validate responses and apply additional properties after all calls succeed.
5. Users review the exported plan and compare stored versions with `diff`.

Raw component variants are not sent to the model. Suggestions do not change
event names, categories, descriptions or Figma sources.

### Cost control
- Haiku is the default; model selection is explicit in config.
- Estimate using the actual batch plan and the known model price table; unknown
  models show an unavailable price. There is no reliable per-screen price promise.
- Default batches contain at most 20 events and 12,000 prompt characters. Failed
  or truncated runs do not apply partial suggestions. AI is disabled by default.

---

## Development

```bash
# Setup
git clone https://github.com/arcbaslow/figma-taxonomy-gen
cd figma-taxonomy-gen
uv sync

# Set tokens
export FIGMA_TOKEN="your-figma-pat"
export ANTHROPIC_API_KEY="your-key"       # optional, for --ai
export AMPLITUDE_API_KEY="your-key"       # optional, for push
export AMPLITUDE_SECRET_KEY="your-secret" # optional, for push
```

---

## Competitive landscape

See the dated, source-linked research in `docs/ROADMAP.md`. Avoid carrying forward
unsupported claims about competitors' features, pricing or maintenance. This
tool's scope is an open-source CLI for generating and reviewing an initial
tracking plan from designs, with configurable names and preserved provenance.

---

## Non-goals (for now)

- Not a Figma plugin (REST API + CLI is simpler, more automatable)
- Not a full tracking plan lifecycle tool (Avo does this well)
- Not a code generator (Ampli CLI / Iteratively handles this)
- Not a real-time sync (webhook-based file watching is v2+)
- Does not handle tracking plan versioning/branching (git does this)

---

## Code conventions

- Python 3.11+, type hints everywhere
- Async where beneficial (Figma API calls)
- No classes where functions suffice
- Config is always a dataclass, never raw dict
- All Figma node IDs preserved in output for traceability
- Tests use fixture files, not live API calls
- Error messages are actionable ("Node 1:234 has no text content - using component name 'Button/Primary' instead")
