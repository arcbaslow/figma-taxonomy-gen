import httpx
import pytest

from figma_taxonomy import figma_client as fc


@pytest.mark.parametrize("kind,header", [("pat", "x-figma-token"), ("plan", "x-figma-token"), ("oauth", "authorization")])
def test_explicit_token_type_uses_only_its_header(kind: str, header: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGMA_TOKEN", "synthetic-token")
    monkeypatch.setenv("FIGMA_TOKEN_TYPE", kind)
    calls = []
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"document": {}, "version": "v1"})
    client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(fc.httpx, "Client", lambda **kwargs: client)
    fc.fetch_file("ABC", no_cache=True)
    assert calls[0].headers[header] == ("Bearer synthetic-token" if kind == "oauth" else "synthetic-token")
    assert ("authorization" in calls[0].headers) != ("x-figma-token" in calls[0].headers)


def test_unknown_token_type_fails_without_network_or_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FIGMA_TOKEN", "synthetic-secret")
    monkeypatch.setenv("FIGMA_TOKEN_TYPE", "guess")
    monkeypatch.setattr(fc.httpx, "Client", lambda **kwargs: pytest.fail("No network"))
    with pytest.raises(ValueError, match="FIGMA_TOKEN_TYPE") as error:
        fc.fetch_file("ABC", no_cache=True)
    assert "synthetic-secret" not in str(error.value)
