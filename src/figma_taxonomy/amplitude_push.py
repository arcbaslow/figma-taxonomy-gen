"""Push a taxonomy to Amplitude via the Taxonomy API (Enterprise-only).

API reference: https://amplitude.com/docs/apis/analytics/taxonomy
Endpoints:
  - GET  /api/2/taxonomy/event             list existing events (for dedup)
  - POST /api/2/taxonomy/category          create category
  - POST /api/2/taxonomy/event-property    create event property
  - POST /api/2/taxonomy/event             create event

Auth: HTTP Basic with (api_key, secret_key).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx

from figma_taxonomy.models import TaxonomyEvent


AMPLITUDE_BASE_URL = "https://amplitude.com"


@dataclass
class PushResult:
    events_created: list[str] = field(default_factory=list)
    events_skipped: list[str] = field(default_factory=list)
    properties_created: list[str] = field(default_factory=list)
    categories_created: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    dry_run: bool = False


def make_client(api_key: str, secret_key: str, base_url: str = AMPLITUDE_BASE_URL) -> httpx.Client:
    return httpx.Client(
        base_url=base_url,
        auth=(api_key, secret_key),
        timeout=30.0,
    )


def _fetch_existing_events(client: httpx.Client) -> set[str]:
    try:
        response = client.get("/api/2/taxonomy/event")
        response.raise_for_status()
        data = response.json().get("data", [])
        return {item.get("event_type") for item in data if item.get("event_type")}
    except httpx.HTTPError:
        # If we can't reach the API, push nothing rather than creating dupes.
        return set()


def _post(client: httpx.Client, path: str, payload: dict, result: PushResult) -> bool:
    try:
        response = client.post(path, data=payload)
    except httpx.HTTPError as e:
        result.errors.append({"path": path, "payload": payload, "error": str(e)})
        return False
    if response.status_code >= 400:
        result.errors.append(
            {"path": path, "payload": payload, "status": response.status_code, "body": response.text}
        )
        return False
    return True


def push_taxonomy(
    events: list[TaxonomyEvent],
    client: httpx.Client,
    dry_run: bool = False,
) -> PushResult:
    """Push events, categories, and properties to Amplitude's Taxonomy API."""
    result = PushResult(dry_run=dry_run)
    existing = _fetch_existing_events(client)

    if dry_run:
        return result

    # 1. Unique categories
    seen_categories: set[str] = set()
    for event in events:
        category = event.flow
        if not category or category in seen_categories:
            continue
        seen_categories.add(category)
        if _post(
            client,
            "/api/2/taxonomy/category",
            {"category_name": category},
            result,
        ):
            result.categories_created.append(category)

    # 2. Unique properties
    seen_properties: set[str] = set()
    for event in events:
        for prop in event.properties:
            if prop.name in seen_properties:
                continue
            seen_properties.add(prop.name)
            payload = {
                "event_property": prop.name,
                "description": prop.description or "",
                "type": prop.type,
            }
            if _post(client, "/api/2/taxonomy/event-property", payload, result):
                result.properties_created.append(prop.name)

    # 3. Events (skip already-present)
    for event in events:
        if event.event_name in existing:
            result.events_skipped.append(event.event_name)
            continue
        payload = {
            "event_type": event.event_name,
            "category_name": event.flow or "",
            "description": event.description or "",
        }
        if _post(client, "/api/2/taxonomy/event", payload, result):
            result.events_created.append(event.event_name)

    return result
