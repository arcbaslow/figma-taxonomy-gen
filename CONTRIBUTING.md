# Contributing

Patches welcome. Keep changes small and focused.

## Setup

```
git clone https://github.com/arcbaslow/figma-taxonomy-gen
cd figma-taxonomy-gen
uv sync --extra dev --extra ai --extra mcp
```

Tokens, all optional depending on what you're touching:

```
export FIGMA_TOKEN="your-figma-pat"
export ANTHROPIC_API_KEY="your-key"        # only for --ai
export AMPLITUDE_API_KEY="your-key"        # only for push
export AMPLITUDE_SECRET_KEY="your-secret"
```

## Before you push

```
uv run ruff check src/ tests/
uv run pytest -v
```

Both must pass. CI runs them on Ubuntu and Windows across Python 3.11 /
3.12 / 3.13, and also verifies the package builds.

## Commit style

Plain imperative sentence, sentence-case acceptable. No Conventional
Commits prefixes (`feat:`, `fix:`, `chore:`). No `Co-Authored-By:`
trailers, no `Generated with...` footers, no emoji.

Examples of the desired tone:

- `honor configured output formats`
- `collapse variant frames sharing a screen name`
- `strip Organisms/ prefix from element names`
- `cap event names at the Amplitude 64-char limit`

PR refs `(#NNN)` only when one exists.

## Code conventions

From `CLAUDE.md`, and they are enforced in review:

- Python 3.11+, type hints everywhere
- Async where it buys something, which mostly means Figma API calls
- No classes where functions suffice
- Config is always a dataclass, never a raw dict
- Every Figma node ID is preserved into the output, for traceability
- Error messages are actionable. `Node 1:234 has no text content -
  using component name 'Button/Primary' instead` beats `extraction
  failed`.

## Tests use fixtures, never the live API

`tests/fixtures/` holds recorded Figma API responses. CI has no Figma
token and must never need one. If you add a case, add a fixture — do
not add a test that hits the network, even guarded.

The same goes for the AI enricher and the Amplitude push: mock the
client, assert on the request you would have sent.

## What I'll accept

- Bug fixes with a regression test
- New interactive-element heuristics, with a fixture showing a real
  design pattern the current rules miss
- New output formats, if they need no heavy dependency
- Naming-convention options that stay configurable rather than
  hardcoded
- Documentation fixes
- CI improvements

## What I'll push back on

- Hardcoding a naming convention that belongs in
  `taxonomy.config.yaml`
- Anything that drops the Figma node ID from output. Traceability back
  to the design is the whole point.
- Making the AI enricher non-optional, or defaulting it on. It costs
  money per run.
- Turning this into a Figma plugin, a full tracking-plan lifecycle
  tool, or a code generator. See the non-goals in `CLAUDE.md`.
- Big rewrites without a discussion first — open an issue describing
  the shape before the work

## Local-only files

- `.figma-taxonomy-cache/` — cached Figma file trees. Real design data.
- `taxonomy.config.yaml` with `api_key` fields filled in. Use the
  environment variables instead.

If you accidentally stage either, `git restore --staged <file>` before
committing.

## License

By contributing you agree your changes are released under the MIT
license, same as the rest of the repo.
