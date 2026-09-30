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
21 events across 6 flows  →  6 API calls
```

## Running it

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
uv pip install 'figma-taxonomy-gen[ai]'
figma-taxonomy extract https://figma.com/design/ABC/App --ai
```

You'll see a cost estimate + confirmation prompt:

```
AI enrichment: 6 call(s), ~3200 input tokens, est. cost $0.0272 (claude-haiku-4-5-20251001)
Proceed? [Y/n]:
```

Skip the prompt in scripts with `--yes`.

## Picking a model

| Model | Standard input / output USD per million tokens |
| --- | --- |
| `claude-haiku-4-5-20251001` (default) | 1 / 5 |
| `claude-sonnet-4-6` | 3 / 15 |
| `claude-opus-4-6` | 5 / 25 |

Prices checked 2026-09-30 against [Anthropic's pricing](https://platform.claude.com/docs/en/about-claude/pricing).
These are the estimator's known models, not a claim that they are the newest
models. The [current model list](https://platform.claude.com/docs/en/models/overview)
also includes Sonnet 5.5 and Opus 5.5. The tool never upgrades your configured model
automatically. Unknown models display an unavailable price estimate and retain
the normal confirmation step (unless `--yes` is supplied).

Set in config:

```yaml
ai:
  enabled: false     # overridden by --ai flag
  model: "claude-sonnet-4-6"
  max_tokens: 2048
```

## Cost estimation

Estimates use four characters per input token and 800 output tokens per flow.
For the example above: 3,200 input tokens at $1/M plus 4,800 output tokens at $5/M
equals $0.0272. This is arithmetic for an assumed workload, not a measured invoice.
Flow size, language, actual response length and SDK retries can change the bill.
`max_tokens` caps each response, not total spending. Per-screen price promises are
not reliable because requests are grouped by page/flow.

## What it doesn't do

- **Doesn't rename events.** Naming is deterministic, from your config. AI only adds
  properties.
- **Doesn't remove properties.** Existing properties (globals, rule-based) are never
  touched.
- **Doesn't verify values.** Enum suggestions are hypotheses inferred from event
  descriptions. Raw component variant metadata is not currently sent to the model.
- **Doesn't run in CI by default.** Every `extract --ai` is a billable call. Gate it
  behind an explicit flag.

## Review workflow

1. Generate once with `--ai`, commit the resulting JSON
2. Generate into a separate output directory and review the diff before replacing
   that file. Regeneration does not load or preserve previous AI suggestions.
3. `--page` can restrict a new run to one page. Otherwise `--ai` enriches every
   generated flow; there is no automatic “new events only” mode.
