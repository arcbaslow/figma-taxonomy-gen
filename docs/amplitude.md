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

Always dry-run before a real push to see what would change:

```bash
figma-taxonomy push output/taxonomy.json --dry-run
```

Dry runs make no requests, including GETs, and require no credentials. Counts
describe the local input and cannot predict which events already exist remotely.

```
Loaded 21 events from output/taxonomy.json

Dry run - would push:
  3 categories: ['Home', 'Login', 'Payments']
  6 properties
  21 events
```

## Real push

```bash
figma-taxonomy push output/taxonomy.json
```

The command:

1. `GET`s the existing event list to avoid duplicates
2. `POST`s unique categories (`/api/2/taxonomy/category`)
3. `POST`s unique event properties (`/api/2/taxonomy/event-property`)
4. `POST`s new events, skipping any that already exist

Event creation sends the documented `category` field. HTTP errors and API bodies
declaring `success: false` are reported as failures. Properties are currently
shared definitions, not event-specific overrides; enum constraints are not pushed.
Repeated category/property creation may produce conflicts. Review these limits
before a real push; the command is not a full tracking-plan synchronization tool.

Errors from the API are collected in a report and printed at the end. A single
failed event doesn't abort the whole push.

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
source of truth; `push` mirrors state into Amplitude. If you want to remove an event
from Amplitude, remove it from Figma, regenerate the taxonomy, and archive the
event in Amplitude manually.

## Recommended cadence

| Trigger                              | What to run                           |
|--------------------------------------|---------------------------------------|
| Every PR                             | `validate --exit-code` (drift check)  |
| Major release / new screen           | `push --dry-run`, review, `push`      |
| New app launch                       | `push` once, then dry-run thereafter  |
