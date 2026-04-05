"""Tests for AI enrichment: prompt building, response parsing, and event merging.

These tests never call the real Anthropic API. A stub client simulates responses.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from figma_taxonomy.ai_enricher import (
    EnrichmentSuggestion,
    build_prompt,
    enrich_events,
    estimate_cost,
    group_events_by_flow,
    parse_suggestions,
)
from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import EventProperty, TaxonomyEvent


def _event(name: str, flow: str = "Onboarding", props: list[str] | None = None) -> TaxonomyEvent:
    return TaxonomyEvent(
        event_name=name,
        flow=flow,
        description="desc",
        source_node_id="1:1",
        properties=[EventProperty(name=p, type="string", description="") for p in (props or [])],
    )


# ---- Grouping ----

def test_group_events_by_flow():
    events = [
        _event("a", "Onboarding"),
        _event("b", "Onboarding"),
        _event("c", "Home"),
    ]
    grouped = group_events_by_flow(events)

    assert set(grouped.keys()) == {"Onboarding", "Home"}
    assert len(grouped["Onboarding"]) == 2
    assert len(grouped["Home"]) == 1


def test_group_events_handles_empty_flow():
    events = [_event("a", "")]
    grouped = group_events_by_flow(events)
    assert "" in grouped or "Uncategorized" in grouped


# ---- Prompt construction ----

def test_prompt_includes_app_context_and_event_names():
    events = [_event("onboarding_phone_entered"), _event("onboarding_otp_entered")]
    prompt = build_prompt("Onboarding", events, app_type="fintech", app_name="MyBank")

    assert "fintech" in prompt.lower()
    assert "MyBank" in prompt
    assert "Onboarding" in prompt
    assert "onboarding_phone_entered" in prompt
    assert "onboarding_otp_entered" in prompt
    assert "json" in prompt.lower()


def test_prompt_lists_existing_properties_so_model_doesnt_duplicate():
    events = [_event("home_card_viewed", props=["screen_name", "card_id"])]
    prompt = build_prompt("Home", events, app_type="fintech", app_name="X")
    assert "screen_name" in prompt
    assert "card_id" in prompt


# ---- Response parsing ----

def test_parse_valid_json_response():
    response = """Here are my suggestions:
```json
{
  "suggestions": [
    {
      "event_name": "onboarding_phone_entered",
      "properties": [
        {"name": "phone_format", "type": "string", "enum": ["local", "international"], "description": "Phone format"},
        {"name": "country_code", "type": "string", "description": "Country calling code"}
      ]
    }
  ]
}
```
"""
    suggestions = parse_suggestions(response)

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.event_name == "onboarding_phone_entered"
    assert len(s.properties) == 2
    assert s.properties[0].name == "phone_format"
    assert s.properties[0].enum_values == ["local", "international"]
    assert s.properties[1].name == "country_code"
    assert s.properties[1].enum_values is None


def test_parse_raw_json_without_code_fence():
    response = '{"suggestions": [{"event_name": "e", "properties": [{"name": "p", "type": "string"}]}]}'
    suggestions = parse_suggestions(response)
    assert len(suggestions) == 1
    assert suggestions[0].event_name == "e"


def test_parse_malformed_json_returns_empty_list():
    suggestions = parse_suggestions("sorry, I can't help with that")
    assert suggestions == []


# ---- Cost estimation ----

def test_estimate_cost_returns_nonzero_for_nonempty_prompts():
    prompts = ["a" * 4000, "b" * 2000]
    estimate = estimate_cost(prompts, model="claude-haiku-4-5-20251001")

    assert estimate["input_chars"] == 6000
    assert estimate["est_input_tokens"] > 0
    assert estimate["est_cost_usd"] > 0
    assert estimate["num_calls"] == 2


def test_estimate_cost_empty():
    estimate = estimate_cost([], model="claude-haiku-4-5-20251001")
    assert estimate["num_calls"] == 0
    assert estimate["est_cost_usd"] == 0.0


def test_estimate_cost_unknown_model_falls_back_to_haiku_pricing():
    estimate = estimate_cost(["x" * 1000], model="some-unknown-model")
    assert estimate["est_cost_usd"] > 0


# ---- End-to-end enrichment with stub client ----

@dataclass
class _StubContent:
    text: str


@dataclass
class _StubResponse:
    content: list


class _StubMessages:
    def __init__(self, response_map: dict[str, str]):
        self.response_map = response_map
        self.calls = []

    def create(self, model, max_tokens, messages):
        self.calls.append({"model": model, "messages": messages})
        # Pick a response based on any matching flow keyword in prompt
        prompt = messages[0]["content"]
        for keyword, response in self.response_map.items():
            if keyword in prompt:
                return _StubResponse(content=[_StubContent(text=response)])
        return _StubResponse(content=[_StubContent(text='{"suggestions": []}')])


class _StubClient:
    def __init__(self, response_map: dict[str, str]):
        self.messages = _StubMessages(response_map)


def test_enrich_events_merges_suggested_properties():
    events = [
        _event("onboarding_phone_entered", flow="Onboarding", props=["screen_name"]),
    ]
    response = """```json
{"suggestions": [{"event_name": "onboarding_phone_entered", "properties": [{"name": "phone_format", "type": "string", "description": "Format"}]}]}
```"""
    client = _StubClient({"Onboarding": response})
    config = TaxonomyConfig()

    enriched = enrich_events(events, config, client=client)

    assert len(enriched) == 1
    prop_names = {p.name for p in enriched[0].properties}
    assert "screen_name" in prop_names  # original kept
    assert "phone_format" in prop_names  # added


def test_enrich_events_does_not_duplicate_existing_properties():
    events = [_event("home_card_viewed", flow="Home", props=["screen_name", "card_id"])]
    response = '{"suggestions": [{"event_name": "home_card_viewed", "properties": [{"name": "card_id", "type": "string"}, {"name": "card_position", "type": "number"}]}]}'
    client = _StubClient({"Home": response})

    enriched = enrich_events(events, TaxonomyConfig(), client=client)

    names = [p.name for p in enriched[0].properties]
    assert names.count("card_id") == 1
    assert "card_position" in names


def test_enrich_events_one_api_call_per_flow():
    events = [
        _event("a", flow="Onboarding"),
        _event("b", flow="Onboarding"),
        _event("c", flow="Home"),
    ]
    client = _StubClient({})

    enrich_events(events, TaxonomyConfig(), client=client)

    assert len(client.messages.calls) == 2  # one per flow


def test_enrich_events_skips_flows_with_no_events():
    events: list = []
    client = _StubClient({})
    enriched = enrich_events(events, TaxonomyConfig(), client=client)
    assert enriched == []
    assert len(client.messages.calls) == 0
