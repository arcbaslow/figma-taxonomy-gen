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

Additionally, any node with a **prototype interaction** (click, hover, drag) attached is automatically classified as interactive regardless of name.

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

Amplitude event names are limited to 64 characters (`max_event_length: 64` in `taxonomy.config.yaml`).

---

## Figma API usage

### Authentication
- Personal Access Token (PAT) via env var `FIGMA_TOKEN`
- OAuth2 flow for MCP server (future)

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

When `--ai` or `--enrich` flag is passed:

1. Batch screen contexts (screen name + list of components + text content)
2. Send to Claude with a structured prompt requesting JSON output
3. Claude infers:
   - Event property names and types
   - Enum values from component variants
   - Business-relevant descriptions
   - Category assignments
4. Merge AI suggestions with rule-based taxonomy
5. Human reviews via markdown diff or interactive CLI

### Cost control
- Claude Haiku for bulk inference (cheap, fast)
- Claude Sonnet for complex screens with many variants
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

| Tool | What it does | Gap this tool fills |
|------|-------------|---------------------|
| Amplitude Event Planner (Figma plugin) | Manual label placement on designs, CSV export | No auto-extraction. Manual work per element. |
| Tracking Plan Companion (Glazed) | AI suggestions from uploaded designs | Proprietary SaaS, no CLI, no Amplitude integration, no config |
| Avo | Full tracking plan lifecycle management | Heavy SaaS product ($$$). No Figma extraction. Requires manual plan creation. |
| Iteratively (now Amplitude) | Type-safe tracking code generation | Requires existing tracking plan. Doesn't generate from design. |
| This tool | Auto-extract from Figma -> taxonomy with configurable naming rules -> multi-format output | Fills the "design to initial tracking plan" gap. Open source. CLI-first. Configurable. |

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
