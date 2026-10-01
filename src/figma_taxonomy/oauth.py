"""Figma OAuth for a user's own app, with native credential storage only."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import secrets
import sys
import time
import webbrowser
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx

SERVICE = "figma-taxonomy-gen.oauth"
ACCOUNT = "default"
CALLBACK_PATH = "/oauth/callback"
TOKEN_BASE = "https://api.figma.com/v1/oauth"


@dataclass
class Session:
    client_id: str
    client_secret: str = field(repr=False)
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: float


def _positive_number(value: Any) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value > 0
    except OverflowError:
        return False


def _valid_token(value: Any) -> bool:
    return isinstance(value, str) and bool(value) and value.isascii() and all(33 <= ord(char) <= 126 for char in value)


def _native_store() -> Any:
    """Select only an OS backend, never configured plaintext/plugin fallbacks."""
    try:
        if sys.platform == "win32":
            from keyring.backends.Windows import WinVaultKeyring
            store = WinVaultKeyring()
            store.persist = "local machine"
            return store
        if sys.platform == "darwin":
            from keyring.backends.macOS import Keyring
            return Keyring()
        if sys.platform.startswith("linux"):
            from keyring.backends.SecretService import Keyring
            return Keyring()
    except ImportError:
        raise RuntimeError("Install figma-taxonomy-gen[oauth] to use managed OAuth login.") from None
    except Exception:
        raise RuntimeError("Cannot open the native credential store; unlock your OS keychain and retry.") from None
    raise RuntimeError("Managed OAuth supports Windows, macOS and Linux Secret Service.")


def _lock_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path.home() / ".cache"
    return base / "figma-taxonomy-gen" / "oauth.lock"


@contextmanager
def _locked_store() -> Iterator[Any]:
    try:
        from filelock import FileLock, Timeout
    except ImportError:
        raise RuntimeError("Install figma-taxonomy-gen[oauth] to use managed OAuth login.") from None
    store = _native_store()
    try:
        lock_path = _lock_path()
        lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with FileLock(lock_path, timeout=30):
            yield store
    except Timeout:
        raise RuntimeError("Another OAuth operation is still running; retry shortly.") from None
    except OSError:
        raise RuntimeError("Cannot lock OAuth storage; check your user cache directory permissions.") from None


def _read(store: Any) -> Session | None:
    try:
        raw = store.get_password(SERVICE, ACCOUNT)
    except Exception:
        raise RuntimeError("Cannot read the native credential store; unlock it and retry.") from None
    if raw is None:
        return None
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("version") != 1:
            raise ValueError
        for name in ("client_id", "client_secret", "access_token", "refresh_token"):
            if not isinstance(data.get(name), str) or not data[name].strip():
                raise ValueError
        expiry = data.get("expires_at")
        if not _positive_number(expiry) or not all(_valid_token(data[key]) for key in ("access_token", "refresh_token")):
            raise ValueError
        return Session(**{key: data[key] for key in Session.__dataclass_fields__})
    except (ValueError, TypeError, KeyError):
        raise RuntimeError("Stored OAuth session is invalid; run 'figma-taxonomy auth login' again.") from None


def _write(store: Any, session: Session) -> None:
    try:
        store.set_password(SERVICE, ACCOUNT, json.dumps({"version": 1, **asdict(session)}))
    except Exception:
        raise RuntimeError("Cannot save OAuth credentials. Unlock the native store and log in again.") from None


def _request_token(client_id: str, client_secret: str, endpoint: str, data: dict[str, str]) -> dict:
    """Do not retry token exchanges or expose server bodies containing credentials."""
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            response = client.post(f"{TOKEN_BASE}/{endpoint}", auth=(client_id, client_secret), data=data)
    except httpx.HTTPError:
        raise RuntimeError("Figma OAuth connection failed; check your connection and retry login/refresh.") from None
    if response.status_code != 200:
        raise RuntimeError(
            f"Figma OAuth {endpoint} failed (HTTP {response.status_code}); check app credentials, "
            "registered redirect and authorization, then log in again."
        )
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError("Figma OAuth returned invalid JSON; log in again.") from None
    if not isinstance(payload, dict):
        raise RuntimeError("Figma OAuth returned an invalid token response; log in again.")
    return payload


def _session(payload: dict, client_id: str, client_secret: str, refresh_token: str = "") -> Session:
    access = payload.get("access_token")
    refresh = payload.get("refresh_token", refresh_token)
    expiry = payload.get("expires_in")
    if (
        not _valid_token(access) or not _valid_token(refresh)
        or str(payload.get("token_type", "")).lower() != "bearer"
        or not _positive_number(expiry)
        or not math.isfinite(time.time() + expiry)
    ):
        raise RuntimeError("Figma OAuth returned incomplete or invalid token fields; log in again.")
    return Session(client_id, client_secret, access, refresh, time.time() + expiry)


def authorization_url(client_id: str, port: int, state: str, verifier: str) -> str:
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    return "https://www.figma.com/oauth?" + urlencode({
        "client_id": client_id, "redirect_uri": f"http://127.0.0.1:{port}{CALLBACK_PATH}",
        "scope": "file_content:read", "state": state, "response_type": "code",
        "code_challenge": challenge, "code_challenge_method": "S256",
    })


def _receive_code(
    port: int, state: str, url: str, open_browser: bool, notify: Callable[[str], None], timeout: float,
) -> str:
    result: dict[str, str] = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass  # Never log callback query strings (authorization codes).

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query, keep_blank_values=True)
            valid_state = len(params.get("state", [])) == 1 and secrets.compare_digest(params["state"][0].encode("utf-8"), state.encode("utf-8"))
            valid_request = (
                len(self.path) <= 8192 and parsed.path == CALLBACK_PATH
                and not parsed.scheme and not parsed.netloc
                and self.headers.get("Host") == f"127.0.0.1:{port}"
                and valid_state
            )
            if not valid_request:
                status, body = 400, b"Invalid OAuth callback. Return to the authorization page."
            elif "error" in params:
                result["error"] = "OAuth authorization was denied; run login again."
                status, body = 400, b"Authorization denied. Return to the terminal."
            elif len(params.get("code", [])) != 1 or not params["code"][0]:
                status, body = 400, b"Missing authorization code."
            else:
                result["code"] = params["code"][0]
                status, body = 200, b"Authorization received. Return to the terminal for the login result."
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    class Listener(HTTPServer):
        allow_reuse_address = False

        def get_request(self) -> tuple:
            connection, address = super().get_request()
            connection.settimeout(1)  # Incomplete local requests cannot hold login open.
            return connection, address

        def handle_error(self, request: Any, client_address: Any) -> None:
            pass  # Do not print callback request context or secrets on disconnect.

    try:
        server = Listener(("127.0.0.1", port), Callback)
    except OSError:
        raise RuntimeError("Cannot bind the OAuth callback port; close the other listener or use --port and register its redirect.") from None
    with server:
        server.timeout = 0.25
        notify(f"Open this URL to authorize Figma access:\n{url}")
        if open_browser:
            try:
                webbrowser.open(url)
            except webbrowser.Error:
                pass  # The printed URL is also usable manually.
        deadline = time.monotonic() + timeout
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if "error" in result:
        raise RuntimeError(result["error"])
    if "code" not in result:
        raise RuntimeError("OAuth login timed out; run login again and authorize in the browser.")
    return result["code"]


def login(
    client_id: str, client_secret: str, *, port: int = 8765, open_browser: bool = True,
    notify: Callable[[str], None] = print, timeout: float = 180,
) -> None:
    if not client_id.strip() or ":" in client_id or not client_secret.strip():
        raise ValueError("Provide a valid OAuth client ID and client secret.")
    if type(port) is not int or not 1024 <= port <= 65535:
        raise ValueError("OAuth callback port must be between 1024 and 65535.")
    if not math.isfinite(timeout) or not 0 < timeout <= 600:
        raise ValueError("OAuth timeout must be between 0 and 600 seconds.")
    with _locked_store() as store:
        # Check store access before launching the browser, without changing a session.
        try:
            store.get_password(SERVICE, ACCOUNT)
        except Exception:
            raise RuntimeError("Cannot read the native credential store; unlock it before login.") from None
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    url = authorization_url(client_id, port, state, verifier)
    code = _receive_code(port, state, url, open_browser, notify, timeout)
    with _locked_store() as store:
        payload = _request_token(client_id, client_secret, "token", {
            "redirect_uri": f"http://127.0.0.1:{port}{CALLBACK_PATH}", "code": code,
            "grant_type": "authorization_code", "code_verifier": verifier,
        })
        _write(store, _session(payload, client_id, client_secret))


def access_token(*, force_refresh: bool = False, rejected_token: str | None = None) -> str:
    with _locked_store() as store:
        session = _read(store)
        if session is None:
            raise RuntimeError("No saved OAuth session. Run 'figma-taxonomy auth login' first.")
        # A concurrent process may already have replaced the rejected token.
        refresh = force_refresh and (rejected_token is None or rejected_token == session.access_token)
        if refresh or session.expires_at <= time.time() + 60:
            payload = _request_token(session.client_id, session.client_secret, "refresh", {"refresh_token": session.refresh_token})
            session = _session(payload, session.client_id, session.client_secret, session.refresh_token)
            _write(store, session)
        return session.access_token


def status() -> dict[str, Any]:
    """Local metadata only; never refresh or expose credentials."""
    with _locked_store() as store:
        session = _read(store)
        return {"logged_in": False} if session is None else {
            "logged_in": True, "expires_at": session.expires_at,
            "expired": session.expires_at <= time.time(),
        }


def logout() -> None:
    """Forget the local session; remote authorization revocation is separate."""
    with _locked_store() as store:
        try:
            if store.get_password(SERVICE, ACCOUNT) is not None:
                store.delete_password(SERVICE, ACCOUNT)
        except Exception:
            raise RuntimeError("Cannot remove the OAuth session; unlock the native credential store and retry.") from None
