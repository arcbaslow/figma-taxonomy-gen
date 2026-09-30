"""Stateful, offline regressions for create-only Amplitude pushes."""

from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from figma_taxonomy.amplitude_push import push_taxonomy
from figma_taxonomy.models import EventProperty, TaxonomyEvent

FIXTURE = Path(__file__).parent / "fixtures" / "amplitude_taxonomy.json"


def _event(name: str = "pay_clicked", prop_type: str = "string") -> TaxonomyEvent:
    return TaxonomyEvent(name, "Checkout", "Pay", [EventProperty("mode", prop_type, "Mode")], "1:1")


def _client(
    state: dict,
    calls: list[httpx.Request],
    intercept: Callable[[httpx.Request], httpx.Response | None] | None = None,
) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if intercept is not None and (response := intercept(request)) is not None:
            return response
        data = {
            k: v[0] for k, v in parse_qs(request.content.decode(), keep_blank_values=True).items()
        }
        path = request.url.path.rsplit("/", 1)[-1]
        if request.method == "GET":
            if path == "category":
                records = state["categories"]
            elif path == "event":
                records = state["events"]
            else:
                # The documented GET uses a form body to scope the association list.
                assert data.get("event_type"), "Never query the unscoped shared-property list"
                records = state["properties"].get(data["event_type"], [])
            return httpx.Response(200, json={"success": True, "data": records})
        assert request.method == "POST", "Create-only policy must not update, delete or restore"
        if path == "category":
            assert not any(c["name"] == data["category_name"] for c in state["categories"])
            state["categories"].append({"name": data["category_name"]})
        elif path == "event":
            assert not any(e["event_type"] == data["event_type"] for e in state["events"])
            state["events"].append({**data, "category": {"name": data["category"]}})
        else:
            assert data.get("event_type"), "Every property must belong to an event"
            assert any(e["event_type"] == data["event_type"] for e in state["events"])
            state["properties"].setdefault(data["event_type"], []).append(data)
        return httpx.Response(200, json={"success": True})

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="https://amplitude.com")


def test_second_push_makes_no_writes_and_scopes_different_schemas() -> None:
    state = {"events": [], "categories": [], "properties": {}}
    calls: list[httpx.Request] = []
    with _client(state, calls) as client:
        events = [_event(), _event("other_clicked", "boolean")]
        first = push_taxonomy(events, client)
        assert not first.errors
        assert first.property_associations_created == [
            ("pay_clicked", "mode"),
            ("other_clicked", "mode"),
        ]
        assert state["properties"]["pay_clicked"][0]["type"] == "string"
        assert state["properties"]["other_clicked"][0]["type"] == "boolean"
        calls.clear()
        second = push_taxonomy(events, client)
    assert not second.errors
    assert calls and all(r.method == "GET" for r in calls)
    assert second.property_associations_skipped == first.property_associations_created
    assert (
        not second.events_created
        and not second.categories_created
        and not second.properties_created
    )


def test_partial_push_resumes_without_recreating_event_and_preserves_sources() -> None:
    state = {"events": [], "categories": [], "properties": {}}
    calls: list[httpx.Request] = []
    fail_property = True

    def intercept(request: httpx.Request) -> httpx.Response | None:
        if (
            fail_property
            and request.method == "POST"
            and request.url.path.endswith("event-property")
        ):
            return httpx.Response(503)
        return None

    event = _event()
    event.source_node_ids.append("2:2")
    original = deepcopy(event)
    with _client(state, calls, intercept) as client:
        first = push_taxonomy([event], client)
        assert first.errors and first.events_created == [event.event_name]
        assert not first.property_associations_created
        fail_property = False
        calls.clear()
        second = push_taxonomy([event], client)
    assert not second.errors
    assert second.property_associations_created == [(event.event_name, "mode")]
    assert [r.url.path for r in calls if r.method == "POST"] == ["/api/2/taxonomy/event-property"]
    assert event == original


@pytest.mark.parametrize(
    "kind,outcome",
    [
        ("category", "match"),
        ("category", "missing"),
        ("event", "match"),
        ("event", "missing"),
        ("event", "different"),
        ("event-property", "match"),
        ("event-property", "missing"),
        ("event-property", "different"),
    ],
)
def test_409_requires_one_verified_readback(kind: str, outcome: str) -> None:
    state = {"events": [], "categories": [], "properties": {}}
    calls: list[httpx.Request] = []

    def intercept(request: httpx.Request) -> httpx.Response | None:
        if request.method != "POST" or request.url.path != f"/api/2/taxonomy/{kind}":
            return None
        data = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        if outcome != "missing":
            if kind == "category":
                state["categories"].append({"name": data["category_name"]})
            elif kind == "event":
                state["events"].append({**data, "category": {"name": data["category"]}})
                if outcome == "different":
                    state["events"][-1]["description"] = "Someone else's description"
            else:
                state["properties"][data["event_type"]] = [data]
                if outcome == "different":
                    data["type"] = "number"
        return httpx.Response(409)

    with _client(state, calls, intercept) as client:
        result = push_taxonomy([_event()], client)
    index = next(i for i, r in enumerate(calls) if r.method == "POST" and r.url.path.endswith(kind))
    assert calls[index + 1].method == "GET" and calls[index + 1].url.path == calls[index].url.path
    assert sum(r.method == "POST" and r.url.path == calls[index].url.path for r in calls) == 1
    if outcome == "match":
        assert not result.errors
        if kind == "event-property":
            assert result.property_associations_skipped == [("pay_clicked", "mode")]
    else:
        assert result.errors
        assert all(r.method == "GET" for r in calls[index + 1 :])


@pytest.mark.parametrize("mode", ["transport", "non-json", "no-success", "declared-failure"])
def test_failed_creation_blocks_dependents_but_allows_independent_events(mode: str) -> None:
    state = {"events": [], "categories": [], "properties": {}}
    calls: list[httpx.Request] = []

    def intercept(request: httpx.Request) -> httpx.Response | None:
        if (
            request.method != "POST"
            or request.url.path != "/api/2/taxonomy/event"
            or b"pay_clicked" not in request.content
        ):
            return None
        if mode == "transport":
            raise httpx.ReadTimeout("simulated timeout", request=request)
        if mode == "non-json":
            return httpx.Response(200, text="Not JSON")
        return httpx.Response(200, json={} if mode == "no-success" else {"success": False})

    with _client(state, calls, intercept) as client:
        result = push_taxonomy([_event(), _event("other_clicked")], client)
    assert result.errors and result.events_created == ["other_clicked"]
    assert result.property_associations_created == [("other_clicked", "mode")]
    assert "pay_clicked" not in state["properties"]


@pytest.mark.parametrize("mode", ["transport", "non-json", "unscoped", "duplicate", "missing-name"])
def test_bad_property_inventory_prevents_even_unrelated_writes(mode: str) -> None:
    state = json.loads(FIXTURE.read_text())
    calls: list[httpx.Request] = []

    def intercept(request: httpx.Request) -> httpx.Response | None:
        if not request.url.path.endswith("event-property"):
            return None
        if mode == "transport":
            raise httpx.ConnectError("simulated failure", request=request)
        if mode == "non-json":
            return httpx.Response(200, text="Not JSON")
        record = deepcopy(state["properties"]["pay_clicked"][0])
        if mode == "unscoped":
            record["event_type"] = "other_clicked"
        if mode == "missing-name":
            record.pop("event_property")
        return httpx.Response(
            200, json={"data": [record, record] if mode == "duplicate" else [record]}
        )

    with _client(state, calls, intercept) as client:
        result = push_taxonomy([_event("new_event"), _event()], client)
    assert result.errors
    assert all(r.method == "GET" for r in calls)


@pytest.mark.parametrize("duplicate", ["event", "property"])
def test_duplicate_local_definitions_fail_before_requests(duplicate: str) -> None:
    events = [_event()]
    if duplicate == "event":
        events.append(_event())
    else:
        events[0].properties.append(events[0].properties[0])
    with _client({}, []) as client:
        assert push_taxonomy(events, client).errors


def test_enum_payload_and_repeat_order_independence() -> None:
    event = _event()
    event.properties[0].enum_values = ["cash", "card"]
    state = json.loads(FIXTURE.read_text())
    calls: list[httpx.Request] = []
    with _client(state, calls) as client:
        reused = push_taxonomy([event], client)
        assert not reused.errors
        assert all(r.method == "GET" for r in calls)
        state["properties"]["pay_clicked"] = []
        created = push_taxonomy([event], client)
    assert not created.errors
    assert state["properties"]["pay_clicked"][0] == {
        "event_type": "pay_clicked",
        "event_property": "mode",
        "description": "Mode",
        "type": "enum",
        "enum_values": "cash,card",
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("type", "boolean"),
        ("enum_values", ["card"]),
        ("description", "Remote"),
        ("is_array_type", True),
    ],
)
def test_existing_property_conflict_never_overwrites(field: str, value: object) -> None:
    state = json.loads(FIXTURE.read_text())
    state["properties"]["pay_clicked"][0][field] = value
    event = _event()
    event.properties[0].enum_values = ["card", "cash"]
    calls: list[httpx.Request] = []
    with _client(state, calls) as client:
        result = push_taxonomy([event], client)
    assert result.errors and "mode" in str(result.errors)
    assert all(r.method == "GET" for r in calls)


@pytest.mark.parametrize(
    "field,value", [("category", {"name": "Remote"}), ("description", "Remote")]
)
def test_event_conflict_blocks_its_properties(field: str, value: object) -> None:
    state = json.loads(FIXTURE.read_text())
    state["events"][0][field] = value
    calls: list[httpx.Request] = []
    with _client(state, calls) as client:
        result = push_taxonomy([_event()], client)
    assert result.errors and "pay_clicked" in str(result.errors)
    assert all(r.method == "GET" for r in calls)


@pytest.mark.parametrize(
    "status,body",
    [(403, {}), (200, {"success": False}), (200, {"success": True}), (200, {"data": "invalid"})],
)
def test_inventory_failure_stops_all_writes(status: int, body: dict) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path.endswith("category"):
            return httpx.Response(status, json=body)
        return httpx.Response(200, json={"success": True, "data": []})

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://amplitude.com"
    ) as client:
        result = push_taxonomy([_event()], client)
    assert result.errors
    assert all(r.method == "GET" for r in calls)


@pytest.mark.parametrize(
    "prop",
    [
        EventProperty("mode", "integer", ""),
        EventProperty("mode", "object", ""),
        EventProperty("mode", "string", "", []),
        EventProperty("mode", "string", "", ["a,b"]),
        EventProperty("mode", "boolean", "", ["true"]),
    ],
)
def test_invalid_schema_is_rejected_even_in_offline_preview(prop: EventProperty) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        pytest.fail("Invalid schema and dry runs must make no requests")

    event = _event()
    event.properties = [prop]
    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://amplitude.com"
    ) as client:
        assert push_taxonomy([event], client, dry_run=True).errors
        assert push_taxonomy([event], client).errors
