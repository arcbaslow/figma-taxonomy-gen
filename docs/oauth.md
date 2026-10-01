# Figma OAuth login

The optional OAuth flow handles browser authorization, code exchange, secure
session storage and refresh for **your own registered Figma app**. An existing
PAT/plan token or externally issued OAuth token in `FIGMA_TOKEN` still works.
This feature is in the current source checkout; no new package release is implied.

## Register and log in

1. Create a Figma OAuth app and enable `file_content:read`. Register the exact
   redirect `http://127.0.0.1:8765/oauth/callback`. If choosing another `--port`,
   register the corresponding redirect before login. App publication and user
   eligibility follow [Figma's OAuth app rules](https://developers.figma.com/docs/rest-api/oauth-apps/).
2. Keep your app's client ID and secret available. This project does not ship an
   app secret or host a callback service for other users.
3. Install the extra and run login from the source checkout:

   ```bash
   uv sync --extra oauth
   uv run figma-taxonomy auth login --client-id YOUR_APP_CLIENT_ID
   ```

The secret prompt hides input. Automation can provide `FIGMA_OAUTH_CLIENT_ID`
and `FIGMA_OAUTH_CLIENT_SECRET` instead; there is no command-line secret option.
Login opens a system browser, requests file-read consent and waits up to 180
seconds. `--no-browser` prints the URL to open manually on the same machine.
`--timeout` accepts 1–600 seconds. Denial, timeout or failed exchange leaves a
previous saved session unchanged; a successful login replaces that one session.

The listener binds only `127.0.0.1`, accepts the registered path/host and validates
an unpredictable state before exchanging a code. S256 PKCE binds the code to this
login. Unrelated/invalid callbacks are rejected while the listener keeps waiting.
The listener closes when authorization completes or the deadline expires.

## Select the saved session

=== "PowerShell"

    ```powershell
    $env:FIGMA_TOKEN_TYPE = "oauth"
    Remove-Item Env:FIGMA_TOKEN -ErrorAction SilentlyContinue
    uv run figma-taxonomy extract https://www.figma.com/design/YOUR_FILE_KEY/MyApp
    ```

=== "Bash"

    ```bash
    export FIGMA_TOKEN_TYPE=oauth
    unset FIGMA_TOKEN
    uv run figma-taxonomy extract https://www.figma.com/design/YOUR_FILE_KEY/MyApp
    ```

An explicit `FIGMA_TOKEN` takes precedence and is never stored or refreshed.
Without `FIGMA_TOKEN_TYPE=oauth`, PAT remains the default. Cached/offline and
fixture operations do not access the credential store. MCP uses the same selection
rules under the OS user running its subprocess; login occurs separately in the CLI.

```bash
uv run figma-taxonomy auth status
uv run figma-taxonomy auth refresh
uv run figma-taxonomy auth logout
```

Status shows local presence, expiry and selection only; it does not validate
remote access or refresh. Logout removes local credentials. Revoke the app's
authorization in Figma separately if desired; logout leaves environment tokens
and cached design files untouched.

## Storage and refresh

Sessions contain the app ID/secret, access token, refresh token and expiry. They
are stored under service `figma-taxonomy-gen.oauth`, account `default`, using
Windows Credential Manager (local-machine persistence), macOS Keychain or Linux
Secret Service. The implementation explicitly selects these native backends;
it does not use plaintext keyring plugins or repository config files. Backend
support follows [Python keyring](https://keyring.readthedocs.io/en/latest/).

The OS store must be available and unlocked. Desktop Linux needs a running
Secret Service session. In a headless environment without a usable store, supply
an externally managed environment token instead. Missing extras or inaccessible
stores fail with instructions; credentials are never silently saved elsewhere.

Before a remote request, access tokens expiring within 60 seconds are refreshed
and saved. A 401 gets at most one refresh and file-request replay; 403 does not
trigger refresh. A per-user process lock serializes local session reads, writes,
refreshes and logout. Its file is `%LOCALAPPDATA%/figma-taxonomy-gen/oauth.lock`
on Windows or `~/.cache/figma-taxonomy-gen/oauth.lock` elsewhere and holds no
credentials. New refresh tokens are saved when returned; omitted refresh tokens
retain the prior value. Failed responses never overwrite the stored session.

Figma refresh can invalidate another access token for the same app/user. The lock
coordinates this machine's processes only; avoid sharing the same app/user session
with independently refreshing machines. Token POSTs use the documented HTTPS
endpoints and Basic app authentication, without automatic retries or redirects.
If a response is lost or saving fails after Figma issues a token, log in again.

## Verification scope

Tests exercise mock token endpoints, synthetic credential storage and a real
loopback listener. They cover state/PKCE, malformed responses, refresh rotation,
concurrency, redaction, environment precedence and CLI/MCP-compatible selection.
No real account, browser consent or OS credential entry was accessed during
development. Registering the redirect and accepting consent in your own account
is still needed to verify live app access.
