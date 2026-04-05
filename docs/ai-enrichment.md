# AI enrichment

Rule-based generation gets you event names and a baseline of properties. It can't
infer things like:

- Enum values from component variants (`card_type: ["debit", "credit", "virtual"]`)
- Contextual identifiers (`loan_product_id`, `merchant_category`)
- State flags that matter for a specific business domain

That's what `--ai` adds.

## How it works

Events are grouped by their **flow** (top-level Figma page). For each flow, one
prompt goes to Claude with:

- App type and name from `config.app`
- The flow name
- Every event in that flow with its description and existing properties

Claude returns a JSON block with suggested properties per event. The CLI merges
suggestions into the taxonomy, skipping any property names that already exist.

```
21 events across 6 flows  →  6 API calls  →  ~$0.001 on Haiku
```

## Running it

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
uv pip install 'figma-taxonomy-gen[ai]'
figma-taxonomy extract https://figma.com/design/ABC/App --ai
```

You'll see a cost estimate + confirmation prompt:

```
AI enrichment: 6 call(s), ~3200 input tokens, est. cost $0.0010 (claude-haiku-4-5-20251001)
Proceed? [Y/n]:
```

Skip the prompt in scripts with `--yes`.

## Picking a model

| Model                           | When to use                                             |
|---------------------------------|---------------------------------------------------------|
| `claude-haiku-4-5-20251001`     | Default. Fine for most fintech/e-commerce taxonomies.   |
| `claude-sonnet-4-6`             | Complex screens with many variants or domain nuance     |
| `claude-opus-4-6`               | When you want the best possible naming and you'll pay   |

Set in config:

```yaml
ai:
  enabled: false     # overridden by --ai flag
  model: "claude-sonnet-4-6"
  max_tokens: 2048
```

## Cost ballpark

| App size                   | Flows | Haiku   | Sonnet  |
|----------------------------|-------|---------|---------|
| Small (5-10 screens)       | 2-3   | <$0.001 | ~$0.005 |
| Medium (30-50 screens)     | 6-10  | ~$0.01  | ~$0.05  |
| Large (100+ screens)       | 20+   | ~$0.05  | ~$0.30  |

Estimates use 4 chars/token and ~800 output tokens per call. Real usage depends on
flow size.

## What it doesn't do

- **Doesn't rename events.** Naming is deterministic, from your config. AI only adds
  properties.
- **Doesn't remove properties.** Existing properties (globals, rule-based) are never
  touched.
- **Doesn't guess at values.** Suggestions are property *schemas*, not actual values —
  enum values come from likely component variants, not data.
- **Doesn't run in CI by default.** Every `extract --ai` is a billable call. Gate it
  behind an explicit flag.

## Review workflow

1. Generate once with `--ai`, commit the resulting JSON
2. On subsequent runs, regenerate **without** `--ai` — existing suggestions persist
   if you've committed them
3. Re-run `--ai` only when adding new screens, to enrich just the new events

Or run with `--ai` every time and let `git diff` show you what changed.
