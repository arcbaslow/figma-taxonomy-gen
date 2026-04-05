"""AI enrichment: infer event properties from screen context using Claude.

The client is duck-typed: anything with a `.messages.create(model, max_tokens, messages)`
call returning an object with `.content[0].text` works. Tests use a stub; production
uses the official `anthropic` SDK client.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.models import EventProperty, TaxonomyEvent


# Approximate per-1M-token pricing in USD, as of 2025. Update when Anthropic pricing changes.
# Kept intentionally conservative.
_MODEL_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6": {"input": 15.00, "output": 75.00},
}
_DEFAULT_PRICING = _MODEL_PRICING["claude-haiku-4-5-20251001"]
_CHARS_PER_TOKEN = 4  # rough heuristic for English + code
_EST_OUTPUT_TOKENS_PER_CALL = 800


@dataclass
class EnrichmentSuggestion:
    """Properties the model suggests adding to an event."""

    event_name: str
    properties: list[EventProperty] = field(default_factory=list)


# ---- Grouping ----

def group_events_by_flow(events: list[TaxonomyEvent]) -> dict[str, list[TaxonomyEvent]]:
    """Bucket events by their top-level flow (page). Empty flows fall under 'Uncategorized'."""
    grouped: dict[str, list[TaxonomyEvent]] = {}
    for event in events:
        key = event.flow or "Uncategorized"
        grouped.setdefault(key, []).append(event)
    return grouped


# ---- Prompt construction ----

_PROMPT_TEMPLATE = """You are a product analytics expert specializing in {app_type} event taxonomies.

App: {app_name}
Flow: {flow}

Below are analytics events generated from a Figma design for this flow. For each event, suggest
additional event properties that would be valuable for product analysts - things like enum values
derived from likely component variants, contextual identifiers, and state flags.

Do NOT suggest properties that are already listed under "existing".
Keep suggestions focused: 1-4 new properties per event, only if genuinely useful.

Events:
{events_block}

Respond with ONLY a JSON object matching this schema (no prose, no markdown fencing required):
{{
  "suggestions": [
    {{
      "event_name": "string (must match one of the event names above)",
      "properties": [
        {{
          "name": "snake_case_name",
          "type": "string | number | boolean",
          "description": "1-sentence description",
          "enum": ["optional", "list", "of", "values"]
        }}
      ]
    }}
  ]
}}
"""


def build_prompt(
    flow: str,
    events: list[TaxonomyEvent],
    app_type: str,
    app_name: str,
) -> str:
    event_lines = []
    for event in events:
        existing = [p.name for p in event.properties]
        event_lines.append(
            f"- {event.event_name}: {event.description}\n"
            f"  existing: {existing}"
        )
    return _PROMPT_TEMPLATE.format(
        app_type=app_type,
        app_name=app_name,
        flow=flow,
        events_block="\n".join(event_lines),
    )


# ---- Response parsing ----

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_suggestions(response_text: str) -> list[EnrichmentSuggestion]:
    """Extract suggestions from a model response. Returns [] on any parse failure."""
    payload: Any = None

    fence_match = _JSON_FENCE_RE.search(response_text)
    candidates = []
    if fence_match:
        candidates.append(fence_match.group(1))
    raw_match = _JSON_OBJECT_RE.search(response_text)
    if raw_match:
        candidates.append(raw_match.group(0))

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
            break
        except json.JSONDecodeError:
            continue

    if not isinstance(payload, dict):
        return []

    suggestions_raw = payload.get("suggestions", [])
    if not isinstance(suggestions_raw, list):
        return []

    suggestions: list[EnrichmentSuggestion] = []
    for item in suggestions_raw:
        if not isinstance(item, dict):
            continue
        event_name = item.get("event_name")
        if not isinstance(event_name, str):
            continue

        props: list[EventProperty] = []
        for prop_raw in item.get("properties", []) or []:
            if not isinstance(prop_raw, dict):
                continue
            name = prop_raw.get("name")
            if not isinstance(name, str):
                continue
            enum_values = prop_raw.get("enum")
            if enum_values is not None and not isinstance(enum_values, list):
                enum_values = None
            props.append(
                EventProperty(
                    name=name,
                    type=prop_raw.get("type", "string"),
                    description=prop_raw.get("description", ""),
                    enum_values=enum_values,
                )
            )
        suggestions.append(EnrichmentSuggestion(event_name=event_name, properties=props))

    return suggestions


# ---- Cost estimation ----

def estimate_cost(prompts: list[str], model: str) -> dict:
    """Rough cost estimate for a batch of prompts. Output tokens are estimated."""
    pricing = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
    input_chars = sum(len(p) for p in prompts)
    est_input_tokens = input_chars // _CHARS_PER_TOKEN
    est_output_tokens = _EST_OUTPUT_TOKENS_PER_CALL * len(prompts)

    input_cost = (est_input_tokens / 1_000_000) * pricing["input"]
    output_cost = (est_output_tokens / 1_000_000) * pricing["output"]

    return {
        "num_calls": len(prompts),
        "input_chars": input_chars,
        "est_input_tokens": est_input_tokens,
        "est_output_tokens": est_output_tokens,
        "est_cost_usd": round(input_cost + output_cost, 4),
        "model": model,
    }


# ---- Enrichment ----

def enrich_events(
    events: list[TaxonomyEvent],
    config: TaxonomyConfig,
    client: Any,
    model: str = "claude-haiku-4-5-20251001",
    max_tokens: int = 2048,
) -> list[TaxonomyEvent]:
    """Merge Claude-suggested properties into each event. Returns a new list (events mutated)."""
    grouped = group_events_by_flow(events)
    by_name: dict[str, TaxonomyEvent] = {e.event_name: e for e in events}

    for flow, flow_events in grouped.items():
        prompt = build_prompt(
            flow=flow,
            events=flow_events,
            app_type=config.app.type,
            app_name=config.app.name,
        )
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        for suggestion in parse_suggestions(text):
            target = by_name.get(suggestion.event_name)
            if target is None:
                continue
            existing_names = {p.name for p in target.properties}
            for prop in suggestion.properties:
                if prop.name in existing_names:
                    continue
                target.properties.append(prop)
                existing_names.add(prop.name)

    return events
