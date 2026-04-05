"""Tests for the Amplitude Taxonomy API push.

Uses httpx.MockTransport so no network is touched.
"""

from __future__ import annotations

import httpx

from figma_taxonomy.amplitude_push import PushResult, push_taxonomy
from figma_taxonomy.models import EventProperty, TaxonomyEvent


def _event(name: str, category: str = "Test", props: list[str] | None = None) -> TaxonomyEvent:
    return TaxonomyEvent(
        event_name=name,
        flow=category,
        description=f"{name} description",
        source_node_id="1:1",
        properties=[
            EventProperty(name=p, type="string", description=f"{p} desc") for p in (props or [])
        ],
    )


def _make_client(handler):
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport, base_url="https://amplitude.com", auth=("k", "s"))


def test_push_creates_events_properties_and_categories():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET" and request.url.path == "/api/2/taxonomy/event":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json={"success": True})

    client = _make_client(handler)
    events = [
        _event("home_pageview", category="Home", props=["screen_name"]),
        _event("home_button_clicked", category="Home", props=["screen_name", "element_text"]),
    ]

    result = push_taxonomy(events, client=client)

    assert isinstance(result, PushResult)
    assert set(result.events_created) == {"home_pageview", "home_button_clicked"}
    assert "Home" in result.categories_created
    assert set(result.properties_created) == {"screen_name", "element_text"}
    assert result.errors == []

    methods_paths = [(m, p) for m, p in calls if m == "POST"]
    # 1 category + 2 properties + 2 events = 5 POSTs
    assert len(methods_paths) == 5


def test_push_skips_events_already_present_in_amplitude():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/api/2/taxonomy/event":
            return httpx.Response(200, json={"data": [{"event_type": "home_pageview"}]})
        return httpx.Response(200, json={"success": True})

    client = _make_client(handler)
    events = [
        _event("home_pageview", category="Home"),
        _event("home_button_clicked", category="Home"),
    ]

    result = push_taxonomy(events, client=client)

    assert result.events_created == ["home_button_clicked"]
    assert result.events_skipped == ["home_pageview"]


def test_push_dry_run_makes_no_post_calls():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        return httpx.Response(200, json={"success": True})

    client = _make_client(handler)
    events = [_event("home_pageview", category="Home")]

    result = push_taxonomy(events, client=client, dry_run=True)

    assert "POST" not in calls
    assert result.events_created == []  # nothing actually pushed
    assert result.dry_run is True


def test_push_collects_api_errors_without_aborting():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        # Fail on event POSTs, succeed on categories/properties
        if "event" in request.url.path and "property" not in request.url.path:
            return httpx.Response(400, json={"error": "bad request"})
        return httpx.Response(200, json={"success": True})

    client = _make_client(handler)
    events = [_event("e1", category="C"), _event("e2", category="C")]

    result = push_taxonomy(events, client=client)

    assert result.events_created == []
    assert len(result.errors) == 2


def test_push_dedupes_category_and_property_posts():
    post_paths = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"data": []})
        post_paths.append(request.url.path)
        return httpx.Response(200, json={"success": True})

    client = _make_client(handler)
    events = [
        _event("a", category="Shared", props=["screen_name"]),
        _event("b", category="Shared", props=["screen_name"]),
    ]

    push_taxonomy(events, client=client)

    # One category, one property, two events = 4 POSTs
    assert len(post_paths) == 4
    assert post_paths.count("/api/2/taxonomy/category") == 1
    assert post_paths.count("/api/2/taxonomy/event-property") == 1
