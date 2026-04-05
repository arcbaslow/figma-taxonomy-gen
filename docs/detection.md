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

## Exclusion patterns

Even if a name matches layer 1, these exclusions drop it:

- `icon` (icons inside buttons, not standalone CTAs)
- `divider`, `separator`
- `placeholder`, `hint`
- `loader`, `spinner`

## Screen name derivation

The "screen" for each event comes from the Figma hierarchy, not the element. Given:

```
Page: "Home"
  Frame: "Home - Default"           → screen: home
  Frame: "Home - With Offer"        → screen: home  (variant, collapses)
  Frame: "Home - Skeleton"          → screen: home  (variant, collapses)
```

Variant collapsing uses `naming.screen_name.strip_suffixes`. Numbered prefixes like
`01 - Welcome` strip to `welcome` when `naming.screen_name.strip_prefixes: true`.

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

Fall back to component name when there's no text, controlled by
`element_name.fallback_to_component_name`.

## When detection goes wrong

If an event you expected isn't showing up:

1. Check the component name in Figma against the pattern list
2. Check for an exclusion (`icon` is a common false-negative trigger)
3. Check that the element is a `COMPONENT`/`INSTANCE`, not a raw `FRAME`
4. Add a prototype interaction to force inclusion
5. Or override by renaming the component to include a keyword like `button`

The fastest debugging path is `figma-taxonomy extract --page "Your Page" -f json` and
inspect which `node_id`s made it through.
