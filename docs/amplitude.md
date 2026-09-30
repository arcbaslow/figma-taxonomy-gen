# Amplitude integration

## Amplitude Data CSV import

Generate the optional import profile using a local fixture or a Figma URL:

```bash
figma-taxonomy extract --fixture tests/fixtures/banking_app.json --format amplitude-csv --output output
```

This writes `taxonomy.amplitude.csv` and its mandatory companion,
`taxonomy.amplitude.json`. The companion retains every control/frame source ID
and the original property schemas. Use it with `validate` or `diff`; only the CSV
is for the Amplitude importer. The existing `csv` format remains the review sheet.

The profile follows the 33-column **Events and event properties** contract in
[Amplitude's CSV documentation](https://amplitude.com/docs/data/csv-import-export),
checked 2026-09-30. It emits one row per event/property association and a row with
blank property fields for an event without properties. Event name, description,
category, property name and description are mapped explicitly; shared property
names on different events keep their individual schemas.

Supported property types are `string`, `number`, `integer`, `boolean`, `any`, and
non-empty string enums. Integers use `number` plus `Number is integer=True`.
String enums use `enum` with comma-separated values. Enum members containing
commas, line breaks, empty values or surrounding whitespace are rejected because
the documented list format provides no escaping contract. Numeric/boolean enums,
arrays, objects, constants and additional constraints are rejected before files
are written. Keep those schemas in JSON or adapt them explicitly for import.

Fields the model does not represent are blank, including owner, visibility,
required/array flags, tags, activity and Amplitude event sources. Figma IDs live
in the companion, not in `Event source`. **This is an initial-plan export, not a
remote-metadata-preserving synchronization tool.** In particular, the documented
blank `Object owner` clears an existing owner; blank property flags are optional
and non-array. Blank `Action` creates or updates matching entities. Review updates
to existing definitions carefully.

In Amplitude Data, choose **Events → Import**, upload the CSV, and review the
`import` branch before merging. No upload, credentials or remote request is part
of local generation. The header fixture comes from the public schema, not an
authenticated template download; real-project UI import acceptance remains
unverified. Property groups and user properties are outside this profile.

For MCP, use `export_taxonomy(..., format="amplitude-csv", output_path="plan.csv")`.
It also writes `plan.json` and returns `companion_path` plus import notes.

## Taxonomy API push

The `push` command writes events, categories, and properties directly to
Amplitude's Taxonomy API. Confirm API access for your project; current public docs
do not establish a universal Enterprise-only restriction. The
[API reference](https://amplitude.com/docs/apis/analytics/taxonomy) describes
tracking-plan schema operations, rather than an obsolete Govern-only integration.
The `amplitude-csv` profile above is independent of Taxonomy API access.

## Setup

1. Get an API key + secret from Amplitude: **Settings → Projects → your project →
   General → API key / Secret key**
2. Export them:

    ```bash
    export AMPLITUDE_API_KEY="..."
    export AMPLITUDE_SECRET_KEY="..."
    ```

## Dry run first

Dry-run before a real push to validate the local input:

```bash
figma-taxonomy push output/taxonomy.json --dry-run
```

Dry runs validate names, types and enum constraints without requests or credentials.
Counts describe the local input; they cannot predict existing definitions or remote
conflicts. A property used on two events counts as two associations.

```
Loaded 21 events from output/taxonomy.json

Dry run - validated local input (remote changes unknown):
  3 categories: ['Home', 'Login', 'Payments']
  77 event/property associations
  21 events
```

## Real push

```bash
figma-taxonomy push output/taxonomy.json
```

The command:

1. Validates the entire local input before contacting Amplitude.
2. Reads events, categories, and the properties associated with each existing input
   event. A failed or malformed initial inventory stops all writes.
3. Creates missing categories and events, in that order. Existing events must match
   the input category and description.
4. Creates missing property associations **after their parent event exists**. Each
   property POST includes `event_type`; each property GET uses the documented form
   body with `event_type`. Shared names on different events can have different schemas.

The policy is **create-only**. Existing event descriptions/categories and property
types/descriptions/enums must match; conflicts produce errors without updates.
Enum order is ignored. Existing array properties conflict with the scalar input
model. Remote fields not modeled here (owners, visibility, required flags, regex,
classifications and tags) are not compared or changed. The API decides whether a
new association creates a shared definition or an event-specific override; the
command never updates a shared definition or sends `overrideScope`.

Supported API types are `string`, `number`, `boolean`, `any`, and string enums.
A string property with `enum` values is sent as `type=enum` with comma-separated
`enum_values`. Enum members must be non-empty strings without commas, line breaks
or surrounding whitespace. Integer, object/array schemas, numeric/boolean enums
and additional local constraints are rejected rather than weakened. The separate
CSV import profile supports integers; API push does not. Figma sources remain in
the local JSON and are not sent as Amplitude metadata.

Repeated pushes reuse matching definitions and make no writes when the plan is
already present. After a partial failure, rerunning can fill missing associations
without recreating their events. A `409` triggers one inventory read; it is counted
as reused only if a matching definition is now visible. Hidden/deleted definitions
can still conflict: review them manually. Push never restores, renames or deletes.
Other failed writes are not automatically retried; HTTP/transport errors, invalid
responses and API-declared failures are collected and cause a nonzero exit.
Failed categories/events block their dependent writes while independent events
can proceed. There is no transaction or rollback across the plan.

Tests use a synthetic inventory fixture and mocked requests. Real-account API
acceptance and project entitlement remain unverified.

## Regions

For EU-hosted Amplitude, pass the regional base URL:

```bash
figma-taxonomy push output/taxonomy.json --base-url https://analytics.eu.amplitude.com
```

## One-way operations

The Taxonomy API plans schema; creating a definition does not ingest an event.
Deletes and renames must be done through the Amplitude UI —
`push` only creates.

Treat Amplitude as the downstream system. The Figma file + `taxonomy.json` is the
source of truth; `push` adds missing definitions to Amplitude. If you want to remove an event
from Amplitude, remove it from Figma, regenerate the taxonomy, and archive the
event in Amplitude manually.

## Recommended cadence

| Trigger                              | What to run                           |
|--------------------------------------|---------------------------------------|
| Every PR                             | `validate --exit-code` (drift check)  |
| Major release / new screen           | `push --dry-run`, review, `push`      |
| New app launch                       | `push` once, then dry-run thereafter  |
