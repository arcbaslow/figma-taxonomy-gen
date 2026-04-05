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

naming:
  style: snake_case
  pattern: "{screen}_{element}_{action}"
  max_event_length: 64     # Amplitude's limit

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

## Naming conventions in practice

The pattern `{screen}_{element}_{action}` runs through three layers of cleaning:

1. **Screen name** — taken from the Figma frame hierarchy (`page → frame`). Numbered
   prefixes like `01 - ` or `Step 1:` are stripped. Variant suffixes like `- Default`
   or `- Dark` collapse so one screen isn't counted twice.
2. **Element name** — if the element has text content (button label, field
   placeholder), that's used. Otherwise the component name is used with common
   prefixes like `Component/` stripped. Final string is snake-cased.
3. **Action** — looked up from `actions.{type}` based on the element's detected type.

### Example

```
Figma:    Page "Onboarding" → Frame "02 - Phone Input" → Input "Phone Number"
Cleaned:  screen="onboarding_phone_input" element="phone_number" action="entered"
Event:    onboarding_phone_input_phone_number_entered
```

If that exceeds `max_event_length`, it's truncated (trailing underscores trimmed).

## Property rules

Rules match against the **event name** using glob patterns (`fnmatch`). A property
added via a rule is deduplicated against globals and against other rules — no
duplicate property names on a single event.

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
