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
  Frame: "01 - Welcome"        -> screen: onboarding_welcome
  Frame: "02 - Phone Input"    -> screen: onboarding_phone
  Frame: "03 - OTP"            -> screen: onboarding_otp
  Frame: "04 - Success"        -> screen: onboarding_success

Page: "Home"
  Frame: "Home - Default"      -> screen: home
  Frame: "Home - With Offer"   -> screen: home (variant, not separate screen)
```

Frame naming conventions are configurable. The tool detects variant frames (same screen, different states) and collapses them.

### 3. Naming convention engine

Amplitude event names are limited to 64 characters (`max_event_length: 64` in `taxonomy.config.yaml`).

---

## Figma API usage

### Authentication
- Personal Access Token (PAT) via env var `FIGMA_TOKEN`
- OAuth2 flow for MCP server (future)

### Limits
- The `nodes` endpoint batches at most 50 IDs per request
- Tier 1 rate limit is roughly 60 requests/min

---

## Amplitude Taxonomy API integration

**Note:** The Taxonomy API is Enterprise-only and was built for the older "Govern" product. As of 2024-2025, it has limited support with the newer "Amplitude Data" tracking plans. The tool primarily outputs CSV for import, but supports direct API push for Enterprise users.

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
- Estimated cost: ~$0.02-0.05 per screen (Haiku), ~$0.10-0.20 per screen (Sonnet)
- Full banking app (30-50 screens): $0.50-2.00 total

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
