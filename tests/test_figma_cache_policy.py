"""Cache tests use synthetic data in isolated temp directories, never design caches."""

from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest

from figma_taxonomy import figma_client as fc

HTTP_CLIENT = httpx.Client

@pytest.fixture
def isolated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fc, "CACHE_DIR", tmp_path / "synthetic-cache")
    monkeypatch.setenv("FIGMA_TOKEN", "test-token")


def _http(monkeypatch: pytest.MonkeyPatch, responses: list) -> tuple[list, list]:
    calls, waits = [], []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        response = responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    client = HTTP_CLIENT(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(fc.httpx, "Client", lambda **kwargs: client)
    monkeypatch.setattr(fc.time, "sleep", waits.append)
    return calls, waits


def _ok() -> httpx.Response:
    return httpx.Response(200, json={"document": {"name": "Счёт"}, "version": "v1"})


def test_cold_fetch_uses_one_request(isolated_cache, monkeypatch: pytest.MonkeyPatch) -> None:
    calls, _ = _http(monkeypatch, [_ok()])
    assert fc.fetch_file("ABC")["version"] == "v1"
    assert len(calls) == 1 and not calls[0].url.query


def test_fresh_cache_is_offline_and_expiry_fetches_once(isolated_cache, monkeypatch: pytest.MonkeyPatch) -> None:
    _http(monkeypatch, [_ok()])
    fc.fetch_file("ABC")
    calls, _ = _http(monkeypatch, [_ok()])
    assert fc.fetch_file("ABC")["document"]["name"] == "Счёт"
    assert not calls
    fc.fetch_file("ABC", cache_ttl=0)
    assert len(calls) == 1


def test_offline_requires_cache_but_no_token(isolated_cache, monkeypatch: pytest.MonkeyPatch) -> None:
    _http(monkeypatch, [_ok()])
    fc.fetch_file("ABC")
    monkeypatch.delenv("FIGMA_TOKEN")
    monkeypatch.setattr(fc.httpx, "Client", Mock(side_effect=AssertionError("No network")))
    assert fc.fetch_file("ABC", offline=True, cache_ttl=0)["version"] == "v1"
    with pytest.raises(RuntimeError, match="offline"):
        fc.fetch_file("MISSING", offline=True)
    with pytest.raises(ValueError, match="no_cache"):
        fc.fetch_file("ABC", offline=True, no_cache=True)


@pytest.mark.parametrize("failure", [
    httpx.Response(429, headers={"Retry-After": "2"}),
    httpx.Response(503), httpx.ReadTimeout("timeout"),
])
def test_bounded_retry_for_transient_gets(isolated_cache, monkeypatch: pytest.MonkeyPatch, failure) -> None:
    calls, waits = _http(monkeypatch, [failure, _ok()])
    assert fc.fetch_file("ABC", no_cache=True)["version"] == "v1"
    assert len(calls) == 2 and len(waits) == 1


def test_long_retry_after_is_not_shortened(isolated_cache, monkeypatch: pytest.MonkeyPatch) -> None:
    calls, waits = _http(monkeypatch, [httpx.Response(429, headers={"Retry-After": "3600"})])
    with pytest.raises(RuntimeError, match="3600"):
        fc.fetch_file("ABC", no_cache=True)
    assert len(calls) == 1 and not waits


def test_retry_count_and_total_wait_are_bounded(isolated_cache, monkeypatch: pytest.MonkeyPatch) -> None:
    calls, waits = _http(monkeypatch, [httpx.Response(503) for _ in range(3)])
    with pytest.raises(RuntimeError, match="503"):
        fc.fetch_file("ABC", no_cache=True)
    assert len(calls) == 3 and sum(waits) <= 10


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_permanent_errors_are_not_retried(isolated_cache, monkeypatch: pytest.MonkeyPatch, status: int) -> None:
    calls, waits = _http(monkeypatch, [httpx.Response(status)])
    with pytest.raises(RuntimeError):
        fc.fetch_file("ABC", no_cache=True)
    assert len(calls) == 1 and not waits


def test_expired_and_corrupt_cache_never_silently_becomes_offline_fallback(isolated_cache, monkeypatch: pytest.MonkeyPatch) -> None:
    _http(monkeypatch, [_ok()])
    fc.fetch_file("ABC")
    monkeypatch.setattr(fc.time, "time", lambda: 10**12)
    calls, _ = _http(monkeypatch, [httpx.Response(403)])
    with pytest.raises(RuntimeError, match="denied"):
        fc.fetch_file("ABC")
    assert len(calls) == 1
    fc._cache_path("ABC", "v1").write_text("broken", encoding="utf-8")
    with pytest.raises(RuntimeError, match="offline"):
        fc.fetch_file("ABC", offline=True)


@pytest.mark.parametrize("ttl", [-1, float("nan"), float("inf")])
def test_invalid_cache_age_fails_before_io(ttl: float, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fc, "_read_cache", Mock(side_effect=AssertionError("No cache access")))
    with pytest.raises(ValueError, match="cache_ttl"):
        fc.fetch_file("ABC", cache_ttl=ttl)


def test_cli_and_mcp_use_fresh_validation_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from click.testing import CliRunner

    from figma_taxonomy import cli, mcp_tools

    options = []
    def fetch(url: str, **kwargs) -> dict:
        options.append(kwargs)
        return {"document": {"children": []}}
    monkeypatch.setattr(cli, "fetch_file", fetch)
    monkeypatch.setattr(mcp_tools, "fetch_file", fetch)
    path = tmp_path / "plan.json"
    path.write_text('{"events": {}}', encoding="utf-8")
    assert CliRunner().invoke(cli.main, ["validate", str(path), "--figma", "ABC"]).exit_code == 0
    mcp_tools.validate_taxonomy_tool({"events": {}}, "ABC")
    assert all(item["cache_ttl"] == 0 for item in options)
    result = CliRunner().invoke(cli.main, ["extract", "ABC", "--offline", "--cache-ttl", "12", "--format", "json", "--output", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert options[-1]["offline"] and options[-1]["cache_ttl"] == 12
