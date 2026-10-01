"""Synthetic OAuth credentials, mocked Figma endpoints, and loopback-only callbacks."""

import base64
import hashlib
import json
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
from click.testing import CliRunner

from figma_taxonomy import figma_client, oauth
from figma_taxonomy.cli import main

pytest.importorskip("filelock")

HTTP_CLIENT = httpx.Client
NATIVE_STORE = oauth._native_store


class MemoryStore:
    def __init__(self) -> None:
        self.raw = None
        self.writes = 0

    def get_password(self, service: str, account: str) -> str | None:
        assert (service, account) == (oauth.SERVICE, oauth.ACCOUNT)
        return self.raw

    def set_password(self, service: str, account: str, value: str) -> None:
        assert (service, account) == (oauth.SERVICE, oauth.ACCOUNT)
        self.raw = value
        self.writes += 1

    def delete_password(self, service: str, account: str) -> None:
        assert (service, account) == (oauth.SERVICE, oauth.ACCOUNT)
        self.raw = None


@pytest.fixture(autouse=True)
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    store = MemoryStore()
    monkeypatch.setattr(oauth, "_native_store", lambda: store)
    monkeypatch.setattr(oauth, "_lock_path", lambda: tmp_path / "locks" / "oauth.lock")
    monkeypatch.setattr(oauth.webbrowser, "open", lambda url: pytest.fail("No real browser"))
    monkeypatch.delenv("FIGMA_TOKEN", raising=False)
    monkeypatch.setenv("FIGMA_TOKEN_TYPE", "oauth")
    monkeypatch.delenv("FIGMA_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("FIGMA_OAUTH_CLIENT_ID", raising=False)
    return store


def save(store: MemoryStore, expiry: float | None = None) -> oauth.Session:
    session = oauth.Session("test-app", "fake-client-secret", "fake-access", "fake-refresh", expiry if expiry is not None else time.time() + 3600)
    store.raw = json.dumps({"version": 1, **asdict(session)})
    return session


def token_response(**overrides) -> dict:
    return {"access_token": "new-access", "refresh_token": "new-refresh", "token_type": "bearer", "expires_in": 3600, **overrides}


def mock_http(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    monkeypatch.setattr(oauth.httpx, "Client", lambda **kwargs: HTTP_CLIENT(transport=httpx.MockTransport(handler), **kwargs))


def test_login_pkce_state_exchange_and_secure_storage(isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    observed = {}

    def receive(port, state, url, open_browser, notify, timeout):
        query = parse_qs(urlsplit(url).query)
        assert query["state"] == [state] and len(state) >= 40
        assert query["scope"] == ["file_content:read"]
        assert query["code_challenge_method"] == ["S256"]
        assert query["redirect_uri"] == ["http://127.0.0.1:8765/oauth/callback"]
        observed.update(query)
        return "fake-code+with/symbols"

    def handler(request):
        assert str(request.url) == oauth.TOKEN_BASE + "/token"
        assert request.method == "POST"
        assert request.headers["authorization"] == "Basic " + base64.b64encode(b"test-app:fake-client-secret").decode()
        assert request.headers["content-type"] == "application/x-www-form-urlencoded"
        form = parse_qs(request.content.decode())
        verifier = form["code_verifier"][0]
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        assert observed["code_challenge"] == [challenge]
        assert form["code"] == ["fake-code+with/symbols"]
        assert form["redirect_uri"] == observed["redirect_uri"]
        assert form["grant_type"] == ["authorization_code"]
        return httpx.Response(200, json=token_response())

    monkeypatch.setattr(oauth, "_receive_code", receive)
    mock_http(monkeypatch, handler)
    oauth.login("test-app", "fake-client-secret")
    assert isolated_store.writes == 1
    assert oauth.access_token() == "new-access"
    assert "fake-client-secret" not in repr(oauth._read(isolated_store))
    assert "new-refresh" not in repr(oauth._read(isolated_store))


@pytest.mark.parametrize("rotated", [False, True])
def test_expiry_refresh_preserves_or_rotates_refresh_token(rotated: bool, isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store, time.time() + 30)
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == oauth.TOKEN_BASE + "/refresh"
        assert parse_qs(request.content.decode()) == {"refresh_token": ["fake-refresh"]}
        result = token_response()
        if not rotated:
            del result["refresh_token"]
        return httpx.Response(200, json=result)

    mock_http(monkeypatch, handler)
    assert oauth.access_token() == "new-access"
    assert oauth.access_token() == "new-access"
    assert len(calls) == 1 and isolated_store.writes == 1
    assert json.loads(isolated_store.raw)["refresh_token"] == ("new-refresh" if rotated else "fake-refresh")


def test_concurrent_refresh_is_serialized(isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store, time.time() - 1)
    calls = []

    def handler(request):
        calls.append(request)
        time.sleep(0.05)
        return httpx.Response(200, json=token_response())

    mock_http(monkeypatch, handler)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: oauth.access_token(), range(2)))
    assert results == ["new-access", "new-access"]
    assert len(calls) == 1
    assert oauth.access_token(force_refresh=True, rejected_token="fake-access") == "new-access"
    assert len(calls) == 1


@pytest.mark.parametrize("payload", [[], {}, {"access_token": "secret"}, token_response(expires_in=-1), token_response(expires_in=True), token_response(expires_in=float("inf")), token_response(expires_in=10**400), token_response(access_token="bad\r\ntoken"), token_response(token_type="basic"), token_response(refresh_token=None)], ids=["list", "empty", "missing", "negative", "bool", "infinity", "huge", "header-injection", "type", "null-refresh"])
def test_bad_token_response_preserves_stored_session(payload, isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store, time.time() - 1)
    previous = isolated_store.raw
    # Raw JSON permits a nonfinite value for the response-validation regression.
    mock_http(monkeypatch, lambda request: httpx.Response(200, content=json.dumps(payload)))
    with pytest.raises(RuntimeError, match="token"):
        oauth.access_token()
    assert isolated_store.raw == previous and isolated_store.writes == 0


@pytest.mark.parametrize("status", [302, 400, 401, 429, 500])
def test_failed_exchange_never_retries_or_leaks_body(status: int, isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store, time.time() - 1)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="fake-client-secret fake-refresh new-access", headers={"location": "https://example.com/never"})

    mock_http(monkeypatch, handler)
    with pytest.raises(RuntimeError) as error:
        oauth.access_token()
    assert str(status) in str(error.value)
    assert "fake-" not in str(error.value) and "new-access" not in str(error.value)
    assert len(calls) == 1 and isolated_store.writes == 0


def test_network_failure_is_sanitized(isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store, time.time() - 1)

    def handler(request):
        raise httpx.ConnectError("fake-client-secret", request=request)

    mock_http(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="connection") as error:
        oauth.access_token()
    assert "fake-client-secret" not in str(error.value)


@pytest.mark.parametrize("raw", ["broken", "[]", '{"version":2}', json.dumps({"version": 1, "expires_at": 10**400})])
def test_corrupt_store_can_be_logged_out(raw: str, isolated_store: MemoryStore) -> None:
    isolated_store.raw = raw
    with pytest.raises(RuntimeError, match="invalid"):
        oauth.status()
    oauth.logout()
    oauth.logout()
    assert oauth.status() == {"logged_in": False}


def test_store_failures_are_sanitized(isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args):
        raise RuntimeError("fake-client-secret")

    monkeypatch.setattr(isolated_store, "get_password", fail)
    with pytest.raises(RuntimeError, match="Cannot read") as error:
        oauth.status()
    assert "fake-client-secret" not in str(error.value)
    monkeypatch.setattr(oauth, "_receive_code", lambda *args: pytest.fail("Do not launch login without store access"))
    with pytest.raises(RuntimeError, match="Cannot read"):
        oauth.login("test-app", "fake-client-secret")


def test_write_failure_does_not_return_unsaved_token(isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store, time.time() - 1)
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=token_response()))

    def fail(*args):
        raise RuntimeError("new-access")

    monkeypatch.setattr(isolated_store, "set_password", fail)
    with pytest.raises(RuntimeError, match="Cannot save") as error:
        oauth.access_token()
    assert "new-access" not in str(error.value)


@pytest.mark.parametrize("reply", ["success", "denied"])
def test_loopback_rejects_bad_callbacks_then_accepts_valid(reply: str, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    ready = Queue()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(oauth._receive_code, port, "test-state", "https://www.figma.com/oauth", False, ready.put, 5)
        ready.get(timeout=3)
        with HTTP_CLIENT(trust_env=False) as client:
            base = f"http://127.0.0.1:{port}"
            for query in ["state=wrong&code=fake-code", "state=test-state&state=other&code=fake-code", "state=%C3%A9&code=fake-code", "state=test-state&code=one&code=two"]:
                assert client.get(base + oauth.CALLBACK_PATH + "?" + query).status_code == 400
            assert client.get(base + "/wrong?state=test-state&code=fake-code").status_code == 400
            assert client.get(base + oauth.CALLBACK_PATH + "?state=test-state&code=fake-code", headers={"Host": "evil.example"}).status_code == 400
            query = {"state": "test-state", "code": "fake-code"} if reply == "success" else {"state": "test-state", "error": "access_denied"}
            response = client.get(base + oauth.CALLBACK_PATH + "?" + urlencode(query))
            assert response.headers["cache-control"] == "no-store"
            assert "fake-code" not in response.text
        if reply == "success":
            assert pending.result(timeout=3) == "fake-code"
        else:
            with pytest.raises(RuntimeError, match="denied"):
                pending.result(timeout=3)
    assert "fake-code" not in capsys.readouterr().err


def test_callback_timeout_and_occupied_port() -> None:
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        port = occupied.getsockname()[1]
        with pytest.raises(RuntimeError, match="Cannot bind"):
            oauth._receive_code(port, "state", "url", False, lambda _: None, 0.01)
    with pytest.raises(RuntimeError, match="timed out"):
        oauth._receive_code(port, "state", "url", False, lambda _: None, 0.01)


def test_cli_status_refresh_logout_and_hidden_login(isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    save(isolated_store)
    mock_http(monkeypatch, lambda request: httpx.Response(200, json=token_response()))
    result = runner.invoke(main, ["auth", "status"])
    assert result.exit_code == 0
    assert json.loads(result.output)["managed_session_selected"]
    assert "fake-" not in result.output
    result = runner.invoke(main, ["auth", "refresh"])
    assert result.exit_code == 0 and "new-access" not in result.output
    assert runner.invoke(main, ["auth", "logout"]).exit_code == 0
    assert isolated_store.raw is None
    observed = []
    monkeypatch.setattr(oauth, "login", lambda *args, **kwargs: observed.append((args, kwargs)))
    result = runner.invoke(main, ["auth", "login", "--client-id", "test-app", "--no-browser"], input="hidden-secret\n")
    assert result.exit_code == 0 and "hidden-secret" not in result.output
    assert observed[0][0] == ("test-app", "hidden-secret")
    assert observed[0][1]["open_browser"] is False


@pytest.mark.parametrize("status", [401, 403])
def test_managed_fetch_refreshes_401_once_but_not_403(status: int, isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store)
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/refresh"):
            return httpx.Response(200, json=token_response())
        if len(calls) == 3:
            assert request.headers["authorization"] == "Bearer new-access"
            return httpx.Response(200, json={"document": {}, "version": "v1"})
        return httpx.Response(status)

    mock_http(monkeypatch, handler)
    if status == 401:
        assert figma_client.fetch_file("ABC", no_cache=True)["version"] == "v1"
        assert len(calls) == 3
    else:
        with pytest.raises(RuntimeError, match="denied"):
            figma_client.fetch_file("ABC", no_cache=True)
        assert len(calls) == 1


def test_repeated_401_stops_after_one_refresh(isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=token_response()) if request.method == "POST" else httpx.Response(401)

    mock_http(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="denied"):
        figma_client.fetch_file("ABC", no_cache=True)
    assert len(calls) == 3


def test_environment_token_never_reads_store_or_refreshes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGMA_TOKEN", "explicit-token")
    monkeypatch.setattr(oauth, "access_token", lambda **kwargs: pytest.fail("Explicit environment token wins"))
    calls = []

    def handler(request):
        calls.append(request)
        assert request.headers["authorization"] == "Bearer explicit-token"
        return httpx.Response(401)

    mock_http(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="denied"):
        figma_client.fetch_file("ABC", no_cache=True)
    assert len(calls) == 1


def test_fixture_and_offline_fetch_never_touch_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oauth, "access_token", lambda **kwargs: pytest.fail("No auth for offline sources"))
    monkeypatch.setattr(figma_client, "_cached_file", lambda *args: {"document": {}})
    assert figma_client.fetch_file("ABC", offline=True) == {"document": {}}
    fixture = Path(__file__).parent / "fixtures" / "banking_app.json"
    assert figma_client.load_fixture(fixture)["document"]


def test_missing_session_has_login_guidance() -> None:
    with pytest.raises(RuntimeError, match="auth login"):
        oauth.access_token()


@pytest.mark.parametrize("platform,module,attribute", [
    ("win32", "keyring.backends.Windows", "WinVaultKeyring"),
    ("darwin", "keyring.backends.macOS", "Keyring"),
    ("linux", "keyring.backends.SecretService", "Keyring"),
])
def test_native_backend_selection_has_no_plugin_fallback(platform: str, module: str, attribute: str, monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = SimpleNamespace()
    monkeypatch.setattr(oauth.sys, "platform", platform)
    monkeypatch.setitem(sys.modules, module, SimpleNamespace(**{attribute: lambda: sentinel}))
    assert NATIVE_STORE() is sentinel
    if platform == "win32":
        assert sentinel.persist == "local machine"


def test_missing_native_backend_reports_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oauth.sys, "platform", "win32")
    monkeypatch.setitem(sys.modules, "keyring.backends.Windows", None)
    with pytest.raises(RuntimeError, match=r"\[oauth\]"):
        NATIVE_STORE()


def test_missing_lock_dependency_reports_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "filelock", None)
    with pytest.raises(RuntimeError, match=r"\[oauth\]"):
        oauth.status()


def test_non_json_response_is_sanitized(isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store, time.time() - 1)
    previous = isolated_store.raw
    mock_http(monkeypatch, lambda request: httpx.Response(200, text="fake-client-secret"))
    with pytest.raises(RuntimeError, match="invalid JSON") as error:
        oauth.access_token()
    assert "fake-client-secret" not in str(error.value)
    assert isolated_store.raw == previous


def test_failed_login_preserves_existing_session(isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store)
    previous = isolated_store.raw
    monkeypatch.setattr(oauth, "_receive_code", lambda *args: "fake-code")
    mock_http(monkeypatch, lambda request: httpx.Response(400, json={"error": "fake-code"}))
    with pytest.raises(RuntimeError, match="HTTP 400"):
        oauth.login("new-app", "new-secret")
    assert isolated_store.raw == previous and isolated_store.writes == 0


def test_status_does_not_refresh_expired_session(isolated_store: MemoryStore, monkeypatch: pytest.MonkeyPatch) -> None:
    save(isolated_store, time.time() - 1)
    monkeypatch.setattr(oauth, "_request_token", lambda *args: pytest.fail("Status must stay offline"))
    result = oauth.status()
    assert result["logged_in"] and result["expired"]
    assert not any("token" in key or "secret" in key for key in result)


@pytest.mark.parametrize("options", [{"port": 80}, {"port": 65536}, {"timeout": 0}, {"timeout": float("inf")}])
def test_login_rejects_invalid_listener_options(options: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oauth, "_receive_code", lambda *args: pytest.fail("Do not start invalid listener"))
    with pytest.raises(ValueError):
        oauth.login("test-app", "fake-client-secret", **options)
