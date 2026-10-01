# Roadmap

Reviewed 2026-09-30 against `dd79a4a` (v0.4.2). This run has owner authorization
for bounded feature work. Estimates are engineering days including tests and docs,
not delivery dates. Evidence below distinguishes code findings from vendor claims.

## Baseline

Read `CLAUDE.md`, `CONTRIBUTING.md`, README, changelog, security policy, published
guides, historical design documents, package code, tests and GitHub workflows.
The `~/.gemini/GEMINI.md` referenced by AGENTS.md was absent.

Windows, Python 3.12.14; `uv sync --extra dev --extra ai --extra mcp` succeeded
with uv 0.12.21 installed locally for this audit. Added the docs extra for its CI
check. Locked SDKs: Anthropic 0.89.0 and MCP 1.27.0.

| Check | Baseline result |
| --- | --- |
| `uv run ruff check src/ tests/` | Passed |
| `uv run pytest -v` | Initially 85 passed / 21 temp-directory permission errors; 106 passed with fresh workspace temp paths |
| `uv build` | Wheel and source distribution built |
| `uv run mkdocs build --strict` | Passed |
| Fixture extraction and `validate --exit-code` | 17 elements, 21 events, no drift |

`ci.yml` runs lint, build and tests on Ubuntu/Windows with Python 3.11–3.13.
`docs.yml` runs the strict docs build. No repository workflow invokes the composite
drift action; its offline CLI equivalent was run additionally. Hosted matrix jobs,
live authentication, paid inference and Amplitude writes were not exercised.
No design cache or credential-bearing config was opened.

## Now

Completed in this run, bugs before the final small detection feature. Each
implementation commit received regression coverage and the full local CI check set.

| Item | Why it matters | Evidence | Effort | Risk |
| --- | --- | --- | --- | --- |
| N1. Correct Figma URL parsing, disable both cache reads and writes with `--no-cache`, and explain auth/rate errors | Fetch the selected branch and avoid persisting private designs when explicitly disabled | Baseline `figma_client.py:27–36` matches the parent before the branch; `:99` writes unconditionally; no client tests. [Authentication](https://developers.figma.com/docs/rest-api/authentication/), [rate limits](https://developers.figma.com/docs/rest-api/rate-limits/) | 1 | Low; malformed inputs become errors |
| N2. Detect named non-component nodes with prototype interactions | A frame called Button must not disappear when a generic clickable frame is detected | Baseline `extractor.py:147–150` requires a missing name match for non-components. Add a synthetic interaction fixture | 0.5 | Low; more expected events |
| N3. Honor naming pattern/style and apply the configured cap and screen action to pageviews | Config must govern generated names, including long screen names | Baseline `taxonomy_engine.py:38` hardcodes the pattern; `:149` bypasses the cap and screen action; `test_config.py` already accepts camelCase | 1 | Medium; previously ignored settings change names; collision policy remains an open question |
| N4. Make Amplitude dry runs offline and correct event category payloads | Preview must work without credentials; categories must arrive on the event | Baseline `amplitude_push.py:70` GETs before dry-run; event POST uses `category_name` instead of documented `category`. [API](https://amplitude.com/docs/apis/analytics/taxonomy) | 0.5 | Low; mock exact bodies and reject API-declared failures |
| N5. Make MCP extraction results usable by export and validate; align page filtering | An implementer should be able to connect the advertised tools without rewriting JSON | Baseline `mcp_tools.py` returns an event list but consumers require a map; tests manually convert it. Missing/excluded page behavior differs from CLI | 1 | Low; accept both existing shapes |
| N6. Correct AI price estimates and the added-property count | Users need a credible billable-run preview and accurate result | Baseline `ai_enricher.py:23` overprices Opus 4.6; unknown models silently use Haiku rates; CLI counts after mutation. [Pricing](https://platform.claude.com/docs/en/about-claude/pricing) | 0.5 | Low; preserve opt-in behavior |
| N7. Carry source node IDs into CSV and Excel review exports; correct import claims | Reviewers need the source design in every output, not only JSON/Markdown | `output/amplitude_csv.py`, `output/excel.py` omit IDs. Current six-column CSV differs from the [Data import schema](https://amplitude.com/docs/data/csv-import-export) | 0.5 | Medium; additive columns affect positional consumers |
| N8. Discover screen frames inside Figma sections | Teams organize screens in sections; those screens currently vanish | Baseline `_find_screens` reads direct page frames only. [SECTION node](https://developers.figma.com/docs/rest-api/file-node-types/). Add a nested-section fixture; retain current variant semantics | 0.5 | Low; additional screens appear |

## Completed follow-up: multiple-source provenance

Implemented after the owner's request to start the roadmap tasks. Every variant
frame is now visited, identical full event names retain all contributing control
IDs, and variant-only controls produce events. Names that collide only after
truncation fail with instructions to change the cap, pattern or control names.

The compatibility contract is additive: `source`/`source_node_id` remains the
first contributing ID, with `sources`/`source_node_ids` storing the full list.
CSV/Excel append a JSON-array `Source Node IDs` column; Markdown lists all IDs.
Description/category selection remains unchanged. Optional AI groups each shared
event once and preserves its sources. Drift compares source membership and uses
any shared ID for unambiguous renames; ambiguous splits/merges are not guessed.

Migration: regenerate and review new events and source additions before updating
the stored baseline. Legacy single-source files still load.

## Completed follow-up: screen identity and pageview provenance

Controls retain their owning page ID and frame ID. Categories come from each
control's page, removing the last-page-wins screen-name map. Existing naming stays
the default; `{page}` is an optional normalized page-name placeholder. If different
pages generate the same event name, extraction fails with guidance to qualify the
pattern or rename screens/pages. Distinct page IDs never merge just because page
names match. Control/pageview name collisions also fail with naming guidance.

CLI and MCP use a separate screen inventory to emit pageviews for empty screens
and retain every variant frame's ID. Included pages and section traversal follow
the same rules as control extraction. Existing two-argument Python generation is
compatible but cannot discover empty frames; callers pass `screens=extract_screens(...)`
for the full inventory. Missing IDs in hand-built inputs are not fabricated.

Migration: expect new pageview sources and empty-screen events. Review those
additions before accepting a regenerated baseline. Frame sources support pageview
rename detection, and category-only changes now fail drift checks. Naming patterns
with cross-page collisions need `{page}` or distinct design names; no automatic
prefix is added based on the current page filter.

## Completed follow-up: Amplitude Data CSV profile

Added opt-in `amplitude-csv` to CLI/config/MCP, keeping the review `csv` and
default formats unchanged. The profile pins all 33 public import headers in a
synthetic fixture derived from the [published schema](https://amplitude.com/docs/data/csv-import-export)
on 2026-09-30. No authenticated template was downloaded and no real project was
imported; account/UI acceptance remains unverified.

Rows preserve event-specific property associations, categories and descriptions.
Simple types, integers and non-empty string enums are supported; unrepresentable
constraints and ambiguous enum delimiters fail before writes. Each CSV has a
mandatory sibling JSON with full Figma sources and original supported schemas.
The import does not misuse Amplitude's `Event source` for node IDs. JSON writing
now explicitly uses UTF-8. Import notes explain that blank owners clear existing
owners, and that blank action creates/updates entities. Remote metadata is not
preserved by this initial-plan profile; review the import branch before merging.

## Completed follow-up: repeatable Amplitude API push

Push now reads categories, events and event-scoped property inventories before
writing. It creates only missing definitions, with events before their property
associations. Property requests always include `event_type`, including the form
body on scoped GETs documented by the [Taxonomy API](https://amplitude.com/docs/apis/analytics/taxonomy).
The same property name can have different schemas on different events. Supported
string enums retain their values, and local unsupported types/constraints fail
before requests, including offline previews.

The update policy is create-only: matching definitions are reused, while event
category/description and property type/description/enum conflicts are reported
without overwriting them. No shared-definition updates, lifecycle operations or
automatic retries of failed writes were added. A 409 gets one inventory read and
is accepted only when a matching definition is visible. Initial inventory errors
block all writes; later failures block dependent writes and permit independent
events to continue. Reruns fill missing associations after partial failures.

Migration: existing plans pushed by the earlier global-property implementation
may need missing associations. Review conflicts manually. CLI counts now report
event/property associations; the Python result retains legacy unique property
names and adds precise association lists. Unmodeled remote metadata is left
untouched. Live account acceptance remains unverified.

## Next

Owner authorized completion of the remaining Next and Later work on 2026-10-01.
Work continues on `roadmap-work` after the previous 14 commits were merged and
pushed to `master`. Non-goals and offline-only service testing remain in effect.

Completed in this continuation: property schema drift. Reports include type,
description and enum changes, preserving enum set semantics and following source
renames. File-to-file diffs also compare extra stored constraints without dropping
them during hydration. CLI and MCP expose an additive `property_schema_changes`
field; property-name additions/removals retain their existing shape.

Completed: Figma request efficiency and bounded retries. A cold/expired fetch
makes one file request; extraction can reuse a five-minute local cache while
validation defaults to fresh data. CLI/MCP expose cache age, explicit offline
use and disabled caching. Three attempts and ten seconds of total retry waiting
bound transient GET recovery; server delays are never shortened. Synthetic cache
tests use isolated temp directories, never the repository's design cache.

Completed: configuration validation and previously ignored options. YAML errors
identify paths/lines, types and unknown keys fail before extraction, output paths
honor config unless explicitly overridden, and disabled label fallback reports
the node requiring text. Screen max-depth is explicitly reserved at its legacy
value 2; unsupported values are rejected rather than assigning new screen semantics.
Nested default property/rule definitions are independent between config instances.

These proposals remain unfinished, in priority order. The provenance and import
profile implementations above are complete. Excluded/undetected controls and
real-account import acceptance are not claimed as covered.

| Proposal | Why / evidence | Effort | Risk / decision needed |
| --- | --- | --- | --- |
| Upgrade within MCP 1.x, then evaluate 2.x separately | Requirement is `mcp>=1.0,<2`, lock 1.27.0; current release list shows 2.2.0 and maintained 1.30.0. [Releases](https://github.com/modelcontextprotocol/python-sdk/releases), [migration](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/migration.md) | 1 / 3–5 | Medium / high: test actual protocol calls and dependency compatibility, not just server construction. Keep `<2` until migration |
| Extend fixture coverage before changing heuristic policy | Nested button labels, icon-only CTAs, interactive descendants of cards/forms, hidden layers, component variant metadata and legacy `transitionNodeID` are untested. `_walk_node` stops at a detected container; `_extract_text_content` only reads immediate children; `variants` is always empty | 2–4 | Medium: collecting every nested node can double-count gestures; exclusions conflict with the broad interaction promise. Decide policy before adding detections |
| Harden optional enrichment against malformed and oversized responses | `parse_suggestions` assumes iterable properties, the merger searches all flows, and one call per flow can exceed the output budget | 1–2 | Medium: add hostile/malformed mock responses, per-flow merge boundaries and reviewed batching; keep AI disabled by default |
| Harden review exports and Windows text I/O | Excel stores arbitrary design strings as cell values and only renders four property pairs; fixture/config readers omit explicit UTF-8. JSON writing is now UTF-8 with a Unicode regression. Formula-like labels and remaining Windows round trips need fixtures | 1–2 | Medium: spreadsheet interpretation risks remain untested; avoid altering cell semantics without tests |

## Later

| Proposal | Why / evidence | Effort | Risk |
| --- | --- | --- | --- |
| Explain detection decisions in an optional report | Implementers could inspect why a node was included/excluded without reading regexes; current `_walk_node` silently skips nodes | 2–3 | Medium: define a stable report without changing event output |
| Configurable detection overrides | Teams could map their own design-system names without a fork; current patterns are module constants | 2–3 | Medium: precedence, validation and false-positive fixtures needed |
| OAuth or plan-token authentication | PAT-only `X-FIGMA-TOKEN` currently matches documented PAT authentication. OAuth uses bearer tokens; organization/enterprise plan tokens became available in July 2026. [Authentication](https://developers.figma.com/docs/rest-api/authentication/), [changelog](https://developers.figma.com/docs/rest-api/changelog/) | 3–5 | High: credential lifecycle and distribution change project scope; proposal only |

## Research notes

Sources accessed 2026-09-30; vendor docs describe contracts, not a live-account test.

- **Figma:** `file_content:read` is the relevant scope; legacy OAuth `file_read`
  is deprecated ([scopes](https://developers.figma.com/docs/rest-api/scopes/)).
  File/tree and node endpoints remain Tier 1. Limits depend on seat and resource
  plan, not a universal 60/min. The current rate-limit page's table and prose
  disagree on low-seat monthly quotas (20 versus 6); report `Retry-After` rather
  than hardcode either number. Dev/Full table entries reach 10/15/20 requests per
  minute on paid plans ([limits](https://developers.figma.com/docs/rest-api/rate-limits/)).
  The repo does not use the nodes endpoint; its claimed universal 50-ID maximum
  was not established by the current [endpoint reference](https://developers.figma.com/docs/rest-api/file-endpoints/).
  `interactions`, `SECTION` and `transitionNodeID` remain documented
  ([node types](https://developers.figma.com/docs/rest-api/file-node-types/)).
  Recent color/stroke additions do not affect fields consumed here. Deprecated
  project endpoints were replaced by folder endpoints, which this client does
  not call ([changelog](https://developers.figma.com/docs/rest-api/changelog/)).
- **Amplitude:** the current reference covers planned schemas, Basic auth and
  the existing US/EU hosts. The old assertion that this is only an obsolete
  Govern API is unsupported. Current documentation does not establish universal
  plan entitlement; confirm access for the target project. A 2025
  [release note](https://amplitude.com/releases/support-activity-tags-visibility-ops-taxonomy-api)
  mentions Enterprise customers, which is not proof of current exclusivity.
  The 64-character setting remains this project's default naming policy; a
  universal Amplitude event-name cap of 64 was not verified.
- **Claude:** default Haiku ID `claude-haiku-4-5-20251001` remains listed.
  Current model overview also lists Sonnet 5.5 and Opus 5.5; do not silently
  upgrade paid runs ([models](https://platform.claude.com/docs/en/models/overview)).
  Standard input/output USD per million tokens: Haiku 4.5 1/5, Sonnet 4.6 3/15,
  Opus 4.6 5/25 ([pricing](https://platform.claude.com/docs/en/about-claude/pricing)).
  Calls are per flow, not screen; six calls at 800 output tokens already cost
  $0.024 on Haiku before input. Per-screen/app-size price promises are unreliable.
  `Anthropic().messages.create(model, max_tokens, messages)` remains documented
  ([SDK](https://github.com/anthropics/anthropic-sdk-python)). Model quality and
  actual token use were not tested with paid calls.
- **MCP:** the server uses 1.x `FastMCP`; 2.x is a separate migration, not a
  version-bound edit. The existing upper bound is appropriate pending that work
  ([upstream guidance](https://github.com/modelcontextprotocol/python-sdk)).

## Comparable tools and rejected directions

| Tool | Verified public description | Implication here |
| --- | --- | --- |
| Avo | Direct Figma frame/section/file import into Journeys, source links and reload, announced May 2026 ([announcement](https://www.avo.app/blog/your-designs-your-tracking-plan-now-connected)) | The old “no Figma extraction” comparison is stale; focus on an inspectable local pipeline |
| Glazed | Figma-based AI suggestions and taxonomy reuse ([product](https://www.glazedanalytics.com/)); describes Amplitude/Segment/Mixpanel integration ([introduction](https://glazedanalytics.com/blog/introducing-glazed-tracking-tool/)) | Do not claim it lacks Amplitude integration; improve fixture-backed extraction and traceable exports here |
| Amplitude Event Planner | Amplitude's [article](https://amplitude.com/blog/analytics-tracking-process) describes the Figma planning workflow | Current plugin maintenance/features were not independently verified; do not claim a current feature gap from an old table |
| Ampli | Pulls a tracking plan into typed instrumentation and checks implementation ([CLI](https://amplitude.com/docs/sdks/ampli/ampli-cli)) | Complement the downstream workflow; do not build a code generator |

Rejected for this run: a Figma plugin, tracking-plan lifecycle/branching service,
code generation, real-time synchronization, and automatic AI enrichment. These
cross explicit non-goals or introduce unsolicited paid calls. MCP 2 migration
remains a proposal requiring contract decisions and broader tests. The separate
CSV importer was implemented in an owner-authorized follow-up. Competing on unverified vendor shortcomings
is also rejected. Small correctness and handoff improvements are the useful gap.

## Execution report

Local branch: `roadmap-work`, created from `master` at `dd79a4a`. Version remains
0.4.2. No push, pull request, tag, publication or live service call was performed.

| Commit | Change | Tests passing before commit |
| --- | --- | --- |
| `25b6532` | Add the researched roadmap and navigation | 106 |
| `c5c1c0f` | Correct Figma branch fetching, cache controls and errors | 117 |
| `d0ca539` | Detect named prototype controls on raw nodes | 118 |
| `51da373` | Honor naming pattern/style, pageview action and cap | 125 |
| `9cdbf81` | Make Amplitude previews offline and correct category writes | 127 |
| `95a7f63` | Accept MCP extraction output in export/validation | 134 |
| `1d9f06a` | Correct optional AI estimates and result counts | 137 |
| `8b2bd31` | Preserve source IDs in CSV/Excel review exports | 138 |
| `03c6368` | Discover screens inside nested sections | 139 |

All rows also passed Ruff, package build, strict docs build, fixture extraction
and offline drift validation. Each bug had a failing regression before its fix;
the section fixture also failed against the previous discovery code. The banking
fixture remains at 17 elements and 21 events with no drift. New fixtures cover
named prototype nodes and nested sections.

Initial-run verification: **139 tests pass** on Windows/Python 3.12.14. Ruff, source and
wheel builds, strict MkDocs and offline drift checks pass. The initial temporary
directory errors were environmental; no test expectations were weakened to fix
them. Runs used `PYTEST_ADDOPTS` to select fresh `tests/.tmp/...` paths and a
writable pytest cache. Check logs are retained outside the Git repository after
the final run.

Unverified: the other five CI OS/Python combinations; live PAT/branch permissions;
actual account rate limits; current Amplitude entitlement and UI imports; paid
model quality, token usage and model availability for an account; the Event
Planner plugin's current maintenance. Vendor contract checks used public web
documentation, not authenticated API calls. The runtime lockfile was not upgraded.
The larger and ambiguous changes remain in Next/Later for the reasons in their
risk columns. No credential-bearing config or design cache was read or staged.

Follow-up verification: **160 tests pass**, including 21 provenance regressions
covering shared/unique variant controls, all exports, legacy inputs, optional
mocked AI enrichment, source-only drift, renames, ambiguous splits/merges, and
truncation errors before writes. The new `variant_sources.json` fixture contains
only synthetic nodes. Twelve new tests failed against the prior implementation
before the fix. Ruff, package builds, strict MkDocs, fixture extraction and offline
drift validation also pass. The banking fixture now retains 18 controls in the
same 21 events, including the second login button's ID.

Screen-identity verification: **181 tests pass**, with 21 additional regression
cases for cross-page conflicts, page-qualified snake/camel names, page filtering,
empty screens/variants, all export formats, pageview renames, legacy source-less
baselines, and category drift through CLI/MCP. Eight initial cases and the category
drift case failed against the previous behavior before their fixes. The synthetic
`screen_identity.json` fixture includes same-named screens on two pages, an empty
variant, a text-only screen in a section, and an excluded page. Ruff, package
builds, strict MkDocs and offline extraction/drift checks pass. The banking demo
still has 18 controls and 21 events, now with frame sources on every pageview.

Amplitude CSV verification: **209 tests pass**, including 28 new profile cases.
Fifteen initial tests failed before implementation. Coverage pins the published
headers, per-event property schemas, enum serialization, integer flags, empty
events/plans, Unicode/quoted/multiline text, both MCP input shapes, companion IDs,
and rejection of unsupported constraints/duplicates before writes. CLI tests
cover configuration and explicit format selection, coexistence with the review
CSV, and no partial output on schema errors. Ruff, package builds, strict MkDocs
and offline drift checks pass. The new `examples/amplitude-data` pair is generated
from the synthetic variant fixture and validates without drift. No account import
or remote write was performed; the runtime lockfile and package version remain
unchanged.

Amplitude push verification: **254 tests pass**, up from 209. Seventeen initial
regressions failed against the earlier implementation. The 45 added cases cover
event-specific schemas, enums, repeat runs without writes, partial-failure
recovery, conflicts, one-read 409 reconciliation, malformed/failed inventories,
dependent-write blocking, local schema rejection, source preservation and CLI
preview/result counts. The inventory fixture is synthetic and every API request
is mocked. Ruff, package builds, strict MkDocs, fixture extraction and offline
drift checks pass. The banking fixture remains at 18 controls and 21 events; its
offline push preview reports 77 event/property associations. No live push,
dependency upgrade or package version change was made.
