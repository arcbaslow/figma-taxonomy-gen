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

# Standard per-1M-token USD pricing checked 2026-09-30:
# https://platform.claude.com/docs/en/about-claude/pricing
_MODEL_PRICING = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
}
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

def plan_batches(
    events: list[TaxonomyEvent], config: TaxonomyConfig,
) -> list[tuple[str, list[TaxonomyEvent], str]]:
    """Plan all calls before spending, shared by the preview and executor."""
    if config.ai.batch_size < 1 or config.ai.max_prompt_chars < 1:
        raise ValueError("AI batch_size and max_prompt_chars must be positive.")
    batches = []
    for flow, flow_events in group_events_by_flow(events).items():
        batch: list[TaxonomyEvent] = []
        for event in flow_events:
            single = build_prompt(flow, [event], config.app.type, config.app.name)
            if len(single) > config.ai.max_prompt_chars:
                raise ValueError(f"Event {event.event_name!r} exceeds ai.max_prompt_chars; shorten its context or raise the prompt limit.")
            candidate = build_prompt(flow, [*batch, event], config.app.type, config.app.name)
            if batch and (len(batch) >= config.ai.batch_size or len(candidate) > config.ai.max_prompt_chars):
                batches.append((flow, batch, build_prompt(flow, batch, config.app.type, config.app.name)))
                batch = []
            batch.append(event)
        if batch:
            batches.append((flow, batch, build_prompt(flow, batch, config.app.type, config.app.name)))
    return batches

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_suggestions(response_text: str) -> list[EnrichmentSuggestion]:
    """Extract suggestions from a model response. Returns [] on any parse failure."""
    payload: Any = None
    if not isinstance(response_text, str) or len(response_text) > 200000:
        return []

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
        if not isinstance(event_name, str) or not event_name.strip():
            continue

        props: list[EventProperty] = []
        raw_properties = item.get("properties")
        if not isinstance(raw_properties, list):
            continue
        for prop_raw in raw_properties:
            if not isinstance(prop_raw, dict):
                continue
            name = prop_raw.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            kind = prop_raw.get("type", "string")
            description = prop_raw.get("description", "")
            if not isinstance(kind, str) or kind not in {"string", "number", "boolean"} or not isinstance(description, str):
                continue
            enum_values = prop_raw.get("enum")
            if enum_values is not None and (
                kind != "string" or not isinstance(enum_values, list) or not enum_values
                or any(not isinstance(v, str) or not v for v in enum_values)
            ):
                continue
            props.append(
                EventProperty(
                    name=name,
                    type=kind,
                    description=description,
                    enum_values=enum_values,
                )
            )
        if props:
            suggestions.append(EnrichmentSuggestion(event_name=event_name, properties=props[:4]))

    return suggestions


# ---- Cost estimation ----

def estimate_cost(prompts: list[str], model: str) -> dict:
    """Rough cost estimate for a batch of prompts. Output tokens are estimated."""
    pricing = _MODEL_PRICING.get(model)
    input_chars = sum(len(p) for p in prompts)
    est_input_tokens = input_chars // _CHARS_PER_TOKEN
    est_output_tokens = _EST_OUTPUT_TOKENS_PER_CALL * len(prompts)

    cost = None
    if pricing is not None:
        input_cost = (est_input_tokens / 1_000_000) * pricing["input"]
        output_cost = (est_output_tokens / 1_000_000) * pricing["output"]
        cost = round(input_cost + output_cost, 4)

    return {
        "num_calls": len(prompts),
        "input_chars": input_chars,
        "est_input_tokens": est_input_tokens,
        "est_output_tokens": est_output_tokens,
        "est_cost_usd": cost,
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
    pending: list[tuple[TaxonomyEvent, EventProperty]] = []
    for flow, batch, prompt in plan_batches(events, config):
        by_name = {event.event_name: event for event in batch}
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise ValueError(f"AI response for {flow!r} was truncated; reduce ai.batch_size or increase ai.max_tokens. No suggestions were applied.")
        blocks = getattr(response, "content", None)
        if not isinstance(blocks, list):
            raise ValueError("AI response has no content list; no suggestions were applied.")
        text = "\n".join(block.text for block in blocks if isinstance(getattr(block, "text", None), str))
        if not text or len(text) > 200000:
            raise ValueError("AI response has no usable text or exceeds the response limit; no suggestions were applied.")
        for suggestion in parse_suggestions(text):
            target = by_name.get(suggestion.event_name)
            if target is None:
                continue
            for prop in suggestion.properties:
                pending.append((target, prop))

    for target, prop in pending:
        if prop.name not in {p.name for p in target.properties}:
            target.properties.append(prop)

    return events
