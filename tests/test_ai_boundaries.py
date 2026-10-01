import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from figma_taxonomy import ai_enricher as ai
from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import TaxonomyEvent


def _response(suggestions: list, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(content=[SimpleNamespace(text=json.dumps({"suggestions": suggestions}))], stop_reason=stop_reason)


@pytest.mark.parametrize("props", [123, True, "text", {"name": "p"}, None])
def test_malformed_property_containers_do_not_crash(props) -> None:
    assert ai.parse_suggestions(json.dumps({"suggestions": [{"event_name": "e", "properties": props}]})) == []


@pytest.mark.parametrize("prop", [
    {"name": ""}, {"name": "p", "type": []}, {"name": "p", "type": "object"},
    {"name": "p", "description": []}, {"name": "p", "enum": [1, 2]},
])
def test_invalid_property_schemas_are_not_added(prop: dict) -> None:
    assert ai.parse_suggestions(json.dumps({"suggestions": [{"event_name": "e", "properties": [prop]}]})) == []


def test_cross_flow_suggestions_cannot_modify_other_flow() -> None:
    events = [TaxonomyEvent("first", "A", ""), TaxonomyEvent("second", "B", "")]
    client = SimpleNamespace(messages=SimpleNamespace(create=Mock(side_effect=[
        _response([{"event_name": "second", "properties": [{"name": "injected"}]}]),
        _response([]),
    ])))
    ai.enrich_events(events, TaxonomyConfig(), client)
    assert not events[1].properties


def test_batch_plan_and_calls_match_and_preserve_sources() -> None:
    config = TaxonomyConfig()
    config.ai.batch_size = 2
    events = [TaxonomyEvent(f"event{i}", "A", "", source_node_id=f"1:{i}") for i in range(5)]
    batches = ai.plan_batches(events, config)
    assert [len(batch[1]) for batch in batches] == [2, 2, 1]
    client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=_response([]))))
    ai.enrich_events(events, config, client)
    assert client.messages.create.call_count == len(batches)
    assert [call.kwargs["messages"][0]["content"] for call in client.messages.create.call_args_list] == [batch[2] for batch in batches]
    assert all(event.source_node_ids == [f"1:{i}"] for i, event in enumerate(events))


def test_oversized_event_fails_before_any_paid_call() -> None:
    client = SimpleNamespace(messages=SimpleNamespace(create=Mock()))
    with pytest.raises(ValueError, match="prompt"):
        ai.enrich_events([TaxonomyEvent("huge", "A", "x" * 20000)], TaxonomyConfig(), client)
    client.messages.create.assert_not_called()


def test_truncated_later_batch_does_not_partially_mutate_events() -> None:
    events = [TaxonomyEvent("first", "A", ""), TaxonomyEvent("second", "B", "")]
    client = SimpleNamespace(messages=SimpleNamespace(create=Mock(side_effect=[
        _response([{"event_name": "first", "properties": [{"name": "new"}]}]),
        _response([], "max_tokens"),
    ])))
    with pytest.raises(ValueError, match="truncated"):
        ai.enrich_events(events, TaxonomyConfig(), client)
    assert all(not event.properties for event in events)


def test_prompt_character_limit_splits_batches() -> None:
    config = TaxonomyConfig()
    config.ai.max_prompt_chars = 1800
    events = [TaxonomyEvent(f"e{i}", "A", "x" * 500) for i in range(3)]
    batches = ai.plan_batches(events, config)
    assert len(batches) == 3
    assert all(len(prompt) <= 1800 for _, _, prompt in batches)


def test_cli_preview_counts_actual_batches(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    import anthropic

    from figma_taxonomy.cli import _run_enrichment

    config = TaxonomyConfig()
    config.ai.batch_size = 1
    events = [TaxonomyEvent("first", "A", ""), TaxonomyEvent("second", "A", "")]
    client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=_response([]))), close=Mock())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-only")
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: client)
    _run_enrichment(events, config, True)
    assert "2 call(s)" in capsys.readouterr().out
    assert client.messages.create.call_count == 2
    client.close.assert_called_once()
