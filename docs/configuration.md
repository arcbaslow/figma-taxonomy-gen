# Configuration

All generation behavior is controlled by `taxonomy.config.yaml`. Without a config file,
sensible defaults are used. Pass a custom config with `-c path/to/config.yaml`.

## Full reference

```yaml
app:
  type: fintech            # fintech | ecommerce | saas | social | media
  name: "MyApp"            # Used in output headers

figma:
  exclude_pages: ["Archive", "Drafts", "Components"]

detection:
  include_hidden: true
  traverse_interactive_children: false
  overrides: []           # Ordered name-glob or exact-node rules; see detection guide

naming:
  style: snake_case
  pattern: "{screen}_{element}_{action}"
  max_event_length: 64     # Project naming policy, configurable

  # Component type -> default action verb
  actions:
    button: "clicked"
    link: "clicked"
    input: "entered"
    toggle: "toggled"
    checkbox: "checked"
    dropdown: "selected"
    tab: "viewed"
    card: "viewed"
    modal: "opened"
    form: "submitted"
    screen: "pageview"

  screen_name:
    strip_prefixes: true   # remove "01 - ", "Step 1:", etc.
    strip_suffixes: ["- Default", "- Light", "- Dark", "- Skeleton"]
    max_depth: 2

  element_name:
    strip_common: ["Component/", "UI/", "Atoms/", "Molecules/", "Organisms/"]
    use_text_content: true
    fallback_to_component_name: true

output:
  formats: ["excel", "csv", "json", "markdown"]
  directory: "./output"

ai:
  enabled: false
  model: "claude-haiku-4-5-20251001"
  max_tokens: 2048
  batch_size: 20           # Maximum events per enrichment call
  max_prompt_chars: 12000 # Maximum complete prompt length

# Added to every event
global_properties:
  - name: "screen_name"
    type: "string"
    description: "Screen where event occurred"
  - name: "platform"
    type: "string"
    enum: ["ios", "android", "web"]
  - name: "app_version"
    type: "string"

# Glob-pattern based property injection
property_rules:
  - match: "*_clicked"
    add:
      - name: "element_text"
        type: "string"
  - match: "*_entered"
    add:
      - name: "field_name"
        type: "string"
      - name: "is_valid"
        type: "boolean"
  - match: "*_fail"
    add:
      - name: "error_description"
        type: "string"
```

## Output formats

Output formats are `excel`, `csv`, `json`, `markdown`, and the opt-in
`amplitude-csv`. The default list is unchanged. Selecting `amplitude-csv` also
writes `taxonomy.amplitude.json` for provenance, even when `json` is not selected.
Use `formats: [csv, amplitude-csv]` to produce both review and import CSVs.
See [the import contract and limits](amplitude.md#amplitude-data-csv-import).

## Naming conventions in practice

The pattern `{screen}_{element}_{action}` runs through three layers of cleaning:

1. **Screen name** — taken from the Figma frame hierarchy (`page → frame`). Numbered
   prefixes like `01 - ` are stripped; `Step 1:` is not currently recognized. Variant suffixes like `- Default`
   or `- Dark` collapse so one screen isn't counted twice.
2. **Element name** — if the element has text content (button label, field
   placeholder), that's used. Otherwise the component name is used with common
   prefixes like `Component/` stripped. Final string is snake-cased.
3. **Action** — looked up from `actions.{type}` based on the element's detected type.

### Example

```
Figma:    Page "Onboarding" → Frame "02 - Phone Input" → Input "Phone Number"
Cleaned:  screen="phone_input" element="phone_number" action="entered"
Event:    phone_input_phone_number_entered
```

If that exceeds `max_event_length`, it's truncated (trailing underscores trimmed).
If two different full names truncate to the same name, generation stops with an
error identifying both names and available node IDs. Increase the cap or adjust
the pattern/control names. Identical full names instead merge their source IDs
into one event within a page, including matches across variant frames.

`style` supports `snake_case` and `camelCase`. The configured `pattern` can reorder
`{page}`, `{screen}`, `{element}` and `{action}`. Pageviews use that pattern with an empty
element and `actions.screen`; the default remains `{screen}_pageview`. The length
cap must be positive and applies after styling. Patterns and styles with invalid
values produce an error. Property-rule patterns must match the resulting style.
The default 64-character cap is a project policy, not a verified universal
Amplitude API limit.

To distinguish Settings screens on Account and Admin pages, use:

```yaml
naming:
  pattern: "{page}_{screen}_{element}_{action}"
```

Their pageviews become `account_settings_pageview` and `admin_settings_pageview`.
The page placeholder uses the normalized page name; it does not add a prefix to
`{screen}` itself. The default pattern stays `{screen}_{element}_{action}`.
Cross-page name collisions require a pattern or design-name change; they never
silently merge categories. Pages whose names normalize identically must be
renamed if their events still collide. A control and a pageview also cannot share
an event name: include `{action}` and keep their configured actions distinct.

## Property rules

Rules match against the **event name** using glob patterns (`fnmatch`). A property
added via a rule is deduplicated against globals and against other rules — no
duplicate property names on a single event.

Rule properties currently take precedence over globals with the same name; among
rules, the first matching definition wins. The page supplies the flow/category,
not an automatic prefix in the screen name. Use `{page}` for an explicit prefix.
`screen_name.max_depth` is a reserved compatibility field: only `2` is accepted.
Screens are page frames, including frames inside sections; arbitrary frame-depth
inference is not implemented. Unsupported values now fail instead of being ignored.

When text naming is enabled, `element_name.fallback_to_component_name: false`
requires a label; unlabeled controls fail with their node ID instead of being
silently dropped. When text naming is disabled, component names are used directly.
`output.directory` is honored relative to the process working directory; explicit
`--output` takes precedence. Config files are UTF-8. Unknown settings, invalid
shapes/types, unsupported formats and malformed naming patterns fail with the
relevant field path before fetching or writing. Property definitions require
unique names within each list; the existing rule-over-global precedence remains.

```yaml
property_rules:
  # Rule priority is match order. First match wins for duplicates.
  - match: "onboarding_*"
    add:
      - name: "onboarding_step"
        type: "number"
  - match: "*_success"
    add:
      - name: "completion_time_ms"
        type: "number"
  - match: "*"
    add:
      - name: "session_id"
        type: "string"
```

## Environment variables

| Variable                | Purpose                              |
|-------------------------|--------------------------------------|
| `FIGMA_TOKEN`           | Figma Personal Access Token          |
| `ANTHROPIC_API_KEY`     | Claude API key (for `--ai`)          |
| `AMPLITUDE_API_KEY`     | Amplitude API key (for `push`)       |
| `AMPLITUDE_SECRET_KEY`  | Amplitude secret (for `push`)        |
