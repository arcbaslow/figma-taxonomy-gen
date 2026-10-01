# Security policy

## Reporting a vulnerability

Open a private security advisory on the repo:
https://github.com/arcbaslow/figma-taxonomy-gen/security/advisories/new

Please do not file public issues for security problems.

## What's in scope

- Token handling in `src/figma_taxonomy/figma_client.py`,
  `oauth.py`, `auth_cli.py`, `ai_enricher.py`, and `amplitude_push.py` — Figma tokens, OAuth app credentials, the
  Anthropic API key, and the Amplitude key/secret pair
- The local file cache under `.figma-taxonomy-cache/`. It holds full
  Figma file trees, which for an unreleased product is commercially
  sensitive.
- Anything that writes a token into generated output — a taxonomy JSON,
  a CSV, a markdown plan, or an `.xlsx`
- The MCP server in `mcp_server.py` / `mcp_tools.py`: an MCP client
  supplies the Figma URL, so path traversal, SSRF against non-Figma
  hosts, and unbounded resource use through the tool surface all count
- Prompt injection through Figma layer names reaching the AI enricher.
  Layer names are attacker-controllable if the design file is shared,
  and they land in a prompt.
- Dependency-chain vulnerabilities in `click`, `httpx`, `pyyaml`,
  `openpyxl`, and the optional `anthropic`, `mcp`, `keyring` and `filelock` dependencies

## What's out of scope

- Misuse of the tool against a Figma file you do not have access to.
  The Figma API enforces that; the tool does not add its own layer.
- Bugs in the upstream Figma, Anthropic, or Amplitude APIs — report
  those to the respective vendors
- Issues that require an attacker with shell access to the user's
  machine
- Poor taxonomy suggestions from the AI enricher. That's a quality
  issue; file a normal bug.

## Where credentials come from

Explicit environment credentials are not persisted by the tool:

- `FIGMA_TOKEN` — Figma PAT, REST API plan token, or externally managed OAuth token
- `ANTHROPIC_API_KEY` — only read when `--ai` is passed
- `AMPLITUDE_API_KEY` / `AMPLITUDE_SECRET_KEY` — only read on `push`

Optional `auth login` is a separate, explicit persistence path: the user's OAuth
app client secret, access token and refresh token are saved together in the native
Windows Credential Manager, macOS Keychain or Linux Secret Service. No plaintext
backend fallback is allowed. The local lock file contains no credentials. OAuth
uses state validation, S256 PKCE and a loopback-only callback with a deadline.
Token exchanges are HTTPS POST requests with Basic app authentication and are
not automatically retried or redirected. Logs and status output omit tokens.
`auth logout` deletes the local session; remote revocation is performed in Figma.
See [OAuth setup](docs/oauth.md) for selection, refresh and concurrency behavior.

`taxonomy.config.yaml` has `api_key` fields for convenience. Leave them
empty and use the environment variables. A config file with a real key
in it is a config file that gets committed.

## A note on the cache

`.figma-taxonomy-cache/` is written with default permissions and holds
complete design files. It is gitignored, but on a shared host treat it
as readable by other local users. Use `--no-cache` if that matters.

## Disclosure timeline

I aim to acknowledge security reports within 7 days and ship a fix or
mitigation within 30 days. For high-severity issues affecting active
users, both windows shrink.
