# Cookbook

Practical recipes for real tracking-plan work.

## Separate tracking plans per platform

Web, iOS, and Android often diverge. Run one extraction per platform:

```yaml title="configs/ios.yaml"
app:
  type: fintech
  name: "MyApp iOS"

global_properties:
  - name: "platform"
    type: "string"
    enum: ["ios"]
  - name: "app_version"
    type: "string"
  - name: "ios_version"
    type: "string"
```

```bash
figma-taxonomy extract https://figma.com/design/IOS/Mobile -c configs/ios.yaml -o tracking/ios/
figma-taxonomy extract https://figma.com/design/WEB/Web -c configs/web.yaml -o tracking/web/
```

## Per-pattern descriptions, not just properties

`property_rules` only adds properties. For event-level descriptions by pattern, use
AI enrichment — Claude rewrites descriptions to be domain-specific.

```bash
figma-taxonomy extract https://figma.com/design/ABC/App --ai --yes
```

## Blocking renames

Sometimes you want to reject PRs that rename events without explicit approval.
Checking `report.renamed` is non-empty in your CI script does this:

```yaml
- uses: arcbaslow/figma-taxonomy-gen/.github/actions/drift-check@v0.4.0
  with:
    taxonomy-path: tracking/taxonomy.json
    figma-url: https://figma.com/design/ABC/App
    figma-token: ${{ secrets.FIGMA_TOKEN }}
  continue-on-error: true
  id: drift

- name: Block renames without override
  if: steps.drift.outcome == 'failure' && !contains(github.event.pull_request.labels.*.name, 'taxonomy-rename-approved')
  run: exit 1
```

Require a `taxonomy-rename-approved` label on the PR to let renames through.

## Taxonomy-as-code review

Commit the Markdown output alongside the JSON so designers and PMs can review
changes in the PR diff:

```bash
figma-taxonomy extract https://figma.com/design/ABC/App -o tracking/
git add tracking/taxonomy.json tracking/taxonomy.md
git commit -m "Refresh tracking plan"
```

GitHub renders `.md` in PR view — stakeholders see the tracking plan as a
readable document, not a JSON blob.

## Multiple apps, shared config

Hoist common settings into a base config, then override per-app:

```yaml title="configs/base.yaml"
naming:
  style: snake_case
  max_event_length: 64
  actions:
    button: "clicked"
    # ...

global_properties:
  - name: "session_id"
    type: "string"
```

```yaml title="configs/banking.yaml"
app:
  type: fintech
  name: "Banking"

property_rules:
  - match: "*_payment_*"
    add:
      - name: "payment_amount_kzt"
        type: "number"
      - name: "payment_method"
        type: "string"
```

YAML doesn't merge configs natively — maintain a base via a small wrapper script
that merges them before calling the CLI, or just duplicate what you need.

## Custom element detection

If your design system uses unusual component names, rename them in Figma or add
a post-extraction rename step. The detection heuristics are in
[`src/figma_taxonomy/extractor.py`](https://github.com/arcbaslow/figma-taxonomy-gen/blob/master/src/figma_taxonomy/extractor.py)
— open a PR or fork if your team has recurring mismatches.

## Verifying the initial taxonomy

When you first generate a taxonomy, eyeball the Markdown output and sanity-check:

- Every interactive element has an event (missing → component name mismatch)
- No duplicate events (same name generated twice → check pattern conflicts)
- Action verbs make sense (a card showing as `_clicked` instead of `_viewed`)
- Global properties are present on every event

If the generated plan looks roughly right, commit it. Iterate on edge cases via PRs.
