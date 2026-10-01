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

Legacy non-empty `transitionNodeID` also counts as a prototype interaction, as
documented in the [Figma node reference](https://developers.figma.com/docs/rest-api/file-node-types/).
Decorative-name exclusions still take precedence by default, including icon-only
CTAs whose names begin with `Icon`.

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
the same full event name within a page share one event with all their source node IDs; controls
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
pattern, or rename the controls.

### Pages and pageviews

The owning page supplies each event's flow/category. Page IDs distinguish pages
even when their display names match. Controls from different pages cannot share
an event name: add `{page}` to `naming.pattern` or rename the screens. `{page}` is
the normalized page name; if page names normalize identically, rename the pages
as well. The default pattern remains unchanged, and qualification is explicit so
filtering to one page does not rename its events.

CLI and MCP inventory every screen frame on included pages, even frames with no
detected controls. Pageviews use the screen frame IDs as sources, combining all
variants within that page. A frame organized inside a section is included; layout
frames inside a screen are not separate screens. Page exclusion and explicit page
selection apply equally to controls and pageviews. Control events retain control
IDs rather than replacing them with frame IDs.

When upgrading an older baseline, expect added pageview sources and new pageviews
for empty screens. Frame IDs allow unambiguous pageview renames to be recognized.
Moving a screen or renaming its page also reports category changes when event
names stay unchanged. Review these changes before accepting the new baseline.

Python callers can pass `screens=extract_screens(figma_file, config)` to
`generate_taxonomy(elements, config, screens=...)` to include the full inventory.
The existing two-argument call still works, deriving known screens from elements;
it cannot discover empty frames. Hand-built elements without frame IDs retain
source-less pageviews rather than inventing IDs. Missing page IDs fall back to
the page name for legacy hand-built inputs.

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

When there is no immediate child label, extraction searches visible nested layout
children. It does not borrow text from independently interactive descendants.
If no text exists, component-name fallback is used unless explicitly disabled;
disabled fallback produces an error containing the node ID.

## Hidden layers and nested controls

`detection.include_hidden: true` preserves the existing default. Set it to `false`
to exclude hidden nodes and their descendants, including hidden screen frames and
sections. The screen inventory and control extraction follow the same policy.

`detection.traverse_interactive_children: false` preserves parent suppression:
a detected card/form/button owns the interaction and its descendants are not
separate controls. Set it to `true` to collect nested controls as well, then review
whether these correspond to independent gestures. Every added control retains
its own source ID. Decorative exclusions still remove entire subtrees.

Instance `componentProperties` entries of type `VARIANT` are retained on extracted
elements as `Name=Value` strings. They do not automatically become event properties
or change AI prompts. Synthetic coverage is in `tests/fixtures/detection_policy.json`.

## When detection goes wrong

If an event you expected isn't showing up:

1. Check the component name in Figma against the pattern list
2. Check for an exclusion (`icon` is a common false-negative trigger)
3. Check that the element is a `COMPONENT`/`INSTANCE`, not a raw `FRAME`
4. Add a prototype interaction to include a raw node that is not excluded
5. Or override by renaming the component to include a keyword like `button`

The fastest debugging path is `figma-taxonomy extract --page "Your Page" -f json` and
inspect which `node_id`s made it through.
