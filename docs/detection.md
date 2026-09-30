# How detection works

Figma nodes don't carry a semantic "this is a button" flag. The tool uses a
three-layer strategy.

## Layer 1: Name patterns

Component names are matched case-insensitively against a curated list:

```python
button, btn, cta
link, anchor
input, field, text_field, search_bar
toggle, switch
checkbox, check_box
radio
dropdown, select, picker
tab, tab_bar
card
modal, dialog, sheet
nav_bar, bottom_nav
carousel, slider
chip, tag, badge
```

## Layer 2: Prototype interactions

Any node with a Figma **prototype interaction** (click, hover, drag, etc.) is classified
as interactive regardless of its name. This catches elements that look like cards or
tiles but are actually clickable.

## Layer 3: Component types

Only these Figma node types are considered:

- `COMPONENT` — the master definition
- `COMPONENT_SET` — a variant container
- `INSTANCE` — a placed instance

Plain `FRAME`, `GROUP`, `TEXT`, and `RECTANGLE` nodes are skipped unless they have a
prototype interaction attached.

Names such as `Button/Continue` and `Link/Terms` retain their inferred type even
on raw frames or text. A node with an interaction and no type match uses
`interactive`. Exclusions below still take precedence.

## Exclusion patterns

Even if a name matches layer 1, these exclusions drop it:

- `icon` (icons inside buttons, not standalone CTAs)
- `divider`, `separator`
- `placeholder`, `hint`
- `loader`, `spinner`

## Screen name derivation

Screens are frames directly under a page or nested inside `SECTION` containers.
Discovery stops at each screen frame, so its internal layout frames do not become
additional screens. Section names do not enter event names; the Figma page still
supplies the flow. This traversal does not use `screen_name.max_depth`, which is
currently a reserved, unused setting.

The "screen" for each event comes from the Figma hierarchy, not the element. Given:

```
Page: "Home"
  Frame: "Home - Default"           → screen: home
  Frame: "Home - With Offer"        → screen: home  (variant, collapses)
  Frame: "Home - Skeleton"          → screen: home  (variant, collapses)
```

The `- With Offer` example requires adding that suffix to the configured list;
it is not a default suffix. Every variant frame is visited. Controls that generate
the same full event name share one event with all their source node IDs; controls
unique to later variants create additional events. The first control supplies the
description and legacy primary source. This also applies to repeated labels in
one frame and names intentionally combined by a custom naming pattern.

Variant collapsing uses `naming.screen_name.strip_suffixes`. Numbered prefixes like
`01 - Welcome` strip to `welcome` when `naming.screen_name.strip_prefixes: true`.

JSON includes both the original `source` field and a `sources` array containing
all `figma:node_id:...` references. Older single-source files still load. When
upgrading, regenerate the taxonomy and review newly discovered variant controls
and source additions before accepting the new baseline. Validation and diff report
source additions/removals as drift; source ordering alone is ignored. A rename
can match through any shared node when both events have a unique correspondence.
Ambiguous splits/merges use unchanged names where possible, otherwise additions
and removals, rather than guessing renames.

Names that differ before truncation but collide at `max_event_length` cause an
actionable error before output is written. Increase the limit, adjust the naming
pattern, or rename the controls. Synthetic pageviews still have no frame sources;
cross-page screen identity remains a separate [roadmap item](ROADMAP.md#next).

## Text content vs component name

When `naming.element_name.use_text_content: true` (the default), the tool prefers the
element's **visible text** over the component name. This matters because:

```
Component: "Button/Primary/Large"
Text:      "Apply Now"
```

With text content, you get `..._apply_now_clicked` (matches the user's mental model).
Without, you'd get `..._button_primary_large_clicked` (bound to the design system,
breaks when the component is restyled).

When there is no immediate child label, extraction falls back to the component
name. `element_name.fallback_to_component_name` is loaded but currently unused.
Nested labels are not searched recursively.

## When detection goes wrong

If an event you expected isn't showing up:

1. Check the component name in Figma against the pattern list
2. Check for an exclusion (`icon` is a common false-negative trigger)
3. Check that the element is a `COMPONENT`/`INSTANCE`, not a raw `FRAME`
4. Add a prototype interaction to include a raw node that is not excluded
5. Or override by renaming the component to include a keyword like `button`

The fastest debugging path is `figma-taxonomy extract --page "Your Page" -f json` and
inspect which `node_id`s made it through.
