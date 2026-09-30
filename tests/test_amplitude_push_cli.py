"""CLI push previews and failures use synthetic JSON and mocked HTTP only."""

import json
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

from figma_taxonomy import amplitude_push
from figma_taxonomy.cli import main


def _stored() -> dict:
    return {
        "events": {
            name: {
                "category": "Checkout",
                "description": "Pay",
                "sources": ["figma:node_id:1:1"],
                "properties": {"mode": {"type": "string", "enum": ["card", "cash"]}},
            }
            for name in ["pay_clicked", "other_clicked"]
        }
    }


def _write(tmp_path: Path, stored: dict) -> Path:
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps(stored), encoding="utf-8")
    return path


def test_offline_preview_counts_associations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AMPLITUDE_API_KEY", raising=False)
    monkeypatch.delenv("AMPLITUDE_SECRET_KEY", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("Dry run must not make requests")

    monkeypatch.setattr(
        amplitude_push,
        "make_client",
        lambda *a, **k: httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://amplitude.com",
        ),
    )
    result = CliRunner().invoke(main, ["push", str(_write(tmp_path, _stored())), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "2 event/property associations" in result.output
    assert "remote changes unknown" in result.output


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "string", "minLength": 1},
        {"type": "integer"},
        {"type": "enum"},
        {"type": ["string", "number"]},
        {"type": "string", "enum": []},
        {"type": "string", "enum": ["cash,card"]},
    ],
)
def test_invalid_preview_fails_before_client_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    schema: dict,
) -> None:
    stored = _stored()
    stored["events"]["pay_clicked"]["properties"]["mode"] = schema
    monkeypatch.setattr(amplitude_push, "make_client", lambda *a, **k: pytest.fail("Invalid input"))
    result = CliRunner().invoke(main, ["push", str(_write(tmp_path, stored)), "--dry-run"])
    assert result.exit_code == 1
    assert "pay_clicked/mode" in result.output


def test_normal_push_reports_association_count_and_error_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AMPLITUDE_API_KEY", "test-key")
    monkeypatch.setenv("AMPLITUDE_SECRET_KEY", "test-secret")
    fail = False

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        if fail and request.url.path.endswith("event-property"):
            return httpx.Response(403)
        return httpx.Response(200, json={"success": True})

    monkeypatch.setattr(
        amplitude_push,
        "make_client",
        lambda *a, **k: httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://amplitude.com",
        ),
    )
    path = _write(tmp_path, _stored())
    success = CliRunner().invoke(main, ["push", str(path)])
    assert success.exit_code == 0, success.output
    assert "2 event/property associations" in success.output
    fail = True
    failure = CliRunner().invoke(main, ["push", str(path)])
    assert failure.exit_code == 1
    assert "0 event/property associations" in failure.output
    assert "2 error(s)" in failure.output
