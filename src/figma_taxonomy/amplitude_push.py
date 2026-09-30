"""Create missing Amplitude definitions without overwriting remote schemas.

Contract: https://amplitude.com/docs/apis/analytics/taxonomy
Property reads and writes are always scoped to their event, including overrides.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from figma_taxonomy.models import TaxonomyEvent

AMPLITUDE_BASE_URL = "https://amplitude.com"
_ROOT = "/api/2/taxonomy/"


@dataclass
class PushResult:
    events_created: list[str] = field(default_factory=list)
    events_skipped: list[str] = field(default_factory=list)
    # Legacy unique names; association lists below are the authoritative counts.
    properties_created: list[str] = field(default_factory=list)
    categories_created: list[str] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)
    dry_run: bool = False
    categories_skipped: list[str] = field(default_factory=list)
    property_associations_created: list[tuple[str, str]] = field(default_factory=list)
    property_associations_skipped: list[tuple[str, str]] = field(default_factory=list)


def make_client(api_key: str, secret_key: str, base_url: str = AMPLITUDE_BASE_URL) -> httpx.Client:
    return httpx.Client(base_url=base_url, auth=(api_key, secret_key), timeout=30.0)


def events_for_push(stored: dict) -> list[TaxonomyEvent]:
    """Validate stored schemas before hydration can silently discard constraints."""
    from figma_taxonomy.validate import _events_from_dict

    if not isinstance(stored, dict) or not isinstance(stored.get("events"), dict):
        raise ValueError("Push input must contain an events schema map.")
    for name, body in stored["events"].items():
        if not isinstance(body, dict) or set(body) - {
            "category",
            "description",
            "source",
            "sources",
            "properties",
        }:
            raise ValueError(f"{name}: unsupported event metadata for push.")
        if not isinstance(body.get("source", ""), str) or not isinstance(
            body.get("sources", []), list
        ):
            raise ValueError(f"{name}: source must be a string and sources a list of strings.")
        if any(not isinstance(source, str) for source in body.get("sources", [])):
            raise ValueError(f"{name}: sources must be strings.")
        properties = body.get("properties", {})
        if not isinstance(properties, dict):
            raise ValueError(f"{name}: properties must be a schema map.")
        for prop, schema in properties.items():
            if not isinstance(schema, dict) or set(schema) - {"type", "description", "enum"}:
                raise ValueError(
                    f"{name}/{prop}: push supports type, description and enum only; retain other constraints in JSON."
                )
    events = _events_from_dict(stored["events"])
    _validate(events)
    return events


def _validate(events: list[TaxonomyEvent]) -> None:
    names: set[str] = set()
    for event in events:
        if not isinstance(event.event_name, str) or not event.event_name.strip():
            raise ValueError("Each event needs a non-empty name.")
        if event.event_name in names:
            raise ValueError(f"Duplicate event {event.event_name!r}; merge it before pushing.")
        names.add(event.event_name)
        if any(
            value is not None and not isinstance(value, str)
            for value in (event.flow, event.description)
        ):
            raise ValueError(f"{event.event_name}: category and description must be strings.")
        properties: set[str] = set()
        for prop in event.properties:
            label = f"{event.event_name}/{prop.name}"
            if not isinstance(prop.name, str) or not prop.name.strip() or prop.name in properties:
                raise ValueError(f"{label}: property names must be non-empty and unique per event.")
            properties.add(prop.name)
            if prop.description is not None and not isinstance(prop.description, str):
                raise ValueError(f"{label}: description must be a string.")
            if not isinstance(prop.type, str) or prop.type not in {
                "string",
                "number",
                "boolean",
                "enum",
                "any",
            }:
                raise ValueError(f"{label}: unsupported API type {prop.type!r}.")
            if prop.enum_values is not None or prop.type == "enum":
                values = prop.enum_values
                if (
                    prop.type not in {"string", "enum"}
                    or not isinstance(values, list)
                    or not values
                    or any(
                        not isinstance(v, str)
                        or not v.strip()
                        or any(c in v for c in ",\r\n")
                        or v != v.strip()
                        for v in values
                    )
                ):
                    raise ValueError(
                        f"{label}: enums require string/enum type and non-empty strings "
                        "without commas, line breaks or surrounding whitespace."
                    )


def _inventory(client: httpx.Client, kind: str, event: str = "") -> dict[str, dict]:
    """Fail closed on unreadable inventory; the API scopes GET with a form body."""
    response = client.request("GET", _ROOT + kind, data={"event_type": event} if event else None)
    response.raise_for_status()
    body = response.json()
    if (
        not isinstance(body, dict)
        or body.get("success") is False
        or not isinstance(body.get("data"), list)
    ):
        raise ValueError(f"Cannot list {kind} for {event!r}; check Taxonomy API access/response.")
    key = {"event": "event_type", "category": "name", "event-property": "event_property"}[kind]
    records: dict[str, dict] = {}
    for item in body["data"]:
        name = item.get(key) if isinstance(item, dict) else None
        if not isinstance(name, str) or not name.strip() or name in records:
            raise ValueError(f"Invalid or duplicate {kind} identifier in inventory for {event!r}.")
        if event and item.get("event_type") != event:
            raise ValueError(f"Unscoped property inventory for {event!r}; refusing writes.")
        records[name] = item
    return records


def _matches(remote: dict, payload: dict) -> bool:
    for key, expected in payload.items():
        if key == "category_name":
            actual = remote.get("name")
        elif key == "category":
            category = remote.get(key)
            actual = category.get("name", "") if isinstance(category, dict) else category or ""
        elif key == "description":
            actual = remote.get(key) or ""
        elif key == "enum_values":
            actual = remote.get(key)
            if isinstance(actual, str):
                actual = actual.split(",")
            if not isinstance(actual, list) or any(not isinstance(v, str) for v in actual):
                return False
            if set(actual) != set(expected.split(",")):
                return False
            continue
        else:
            actual = remote.get(key)
        if actual != expected:
            return False
    return not ("event_property" in payload and remote.get("is_array_type"))


def _ensure(
    client: httpx.Client,
    kind: str,
    name: str,
    payload: dict,
    inventory: dict[str, dict],
    reload: Callable[[], dict[str, dict]],
    result: PushResult,
) -> str:
    """Create once; reconcile a 409 with one read, never blindly treat it as success."""
    try:
        if name not in inventory:
            response = client.post(_ROOT + kind, data=payload)
            if response.status_code == 409:
                inventory.update(reload())
                if name not in inventory:
                    raise ValueError(
                        "409 conflict is not visible in inventory; review hidden/deleted definitions before retrying."
                    )
            else:
                response.raise_for_status()
                body = response.json()
                if not isinstance(body, dict) or body.get("success") is not True:
                    raise ValueError(
                        "API did not confirm creation; check project access and payload before retrying."
                    )
                inventory[name] = {**payload, "name": payload.get("category_name")}
                return "created"
        if not _matches(inventory[name], payload):
            raise ValueError(
                "Existing definition differs in category, description or property schema; review it manually. No update was made."
            )
        return "skipped"
    except (httpx.HTTPError, ValueError) as exc:
        result.errors.append({"path": _ROOT + kind, "payload": payload, "error": str(exc)})
        return "failed"


def push_taxonomy(
    events: list[TaxonomyEvent],
    client: httpx.Client,
    dry_run: bool = False,
) -> PushResult:
    """Validate locally, then create missing categories, events and associations.

    Reuse only matching definitions. A failed initial inventory prevents all writes;
    later failures block dependent writes while allowing independent events to proceed.
    Dry runs validate schemas without making any requests or promising remote changes.
    """
    result = PushResult(dry_run=dry_run)
    try:
        _validate(events)
    except ValueError as exc:
        result.errors.append({"error": str(exc)})
        return result
    if dry_run or not events:
        return result
    try:
        existing = _inventory(client, "event")
        categories = _inventory(client, "category")
        properties = {
            e.event_name: _inventory(client, "event-property", e.event_name)
            for e in events
            if e.event_name in existing and e.properties
        }
    except (httpx.HTTPError, ValueError) as exc:
        result.errors.append({"error": f"Inventory failed; no writes made: {exc}"})
        return result

    category_status: dict[str, str] = {}
    for event in events:
        name = event.event_name
        if name not in existing and event.flow:
            if event.flow not in category_status:
                status = _ensure(
                    client,
                    "category",
                    event.flow,
                    {"category_name": event.flow},
                    categories,
                    lambda: _inventory(client, "category"),
                    result,
                )
                category_status[event.flow] = status
                if status != "failed":
                    getattr(result, "categories_" + status).append(event.flow)
            if category_status[event.flow] == "failed":
                continue
        status = _ensure(
            client,
            "event",
            name,
            {
                "event_type": name,
                "category": event.flow or "",
                "description": event.description or "",
            },
            existing,
            lambda: _inventory(client, "event"),
            result,
        )
        if status == "failed":
            continue
        getattr(result, "events_" + status).append(name)
        if status == "skipped" and name not in properties and event.properties:
            # A concurrent creator may have added the event after our initial snapshot.
            try:
                properties[name] = _inventory(client, "event-property", name)
            except (httpx.HTTPError, ValueError) as exc:
                result.errors.append({"event": name, "error": str(exc)})
                continue
        event_properties = properties.setdefault(name, {})
        for prop in event.properties:
            payload = {
                "event_type": name,
                "event_property": prop.name,
                "description": prop.description or "",
                "type": prop.type,
            }
            if prop.enum_values is not None:
                payload.update(type="enum", enum_values=",".join(prop.enum_values))
            status = _ensure(
                client,
                "event-property",
                prop.name,
                payload,
                event_properties,
                lambda: _inventory(client, "event-property", name),
                result,
            )
            if status != "failed":
                getattr(result, "property_associations_" + status).append((name, prop.name))
            if status == "created" and prop.name not in result.properties_created:
                result.properties_created.append(prop.name)
    return result
