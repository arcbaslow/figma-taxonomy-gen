# Amplitude push

The `push` command writes events, categories, and properties directly to
Amplitude's Taxonomy API. Confirm API access for your project; current public docs
do not establish a universal Enterprise-only restriction. The
[API reference](https://amplitude.com/docs/apis/analytics/taxonomy) describes
tracking-plan schema operations, rather than an obsolete Govern-only integration.
The CSV export is a review format; it is not the current Amplitude Data import
template. See the [roadmap](ROADMAP.md#next) for a dedicated import profile.

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
