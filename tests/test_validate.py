"""Tests for taxonomy validation / drift detection."""

from __future__ import annotations

from figma_taxonomy.models import EventProperty, TaxonomyEvent
from figma_taxonomy.validate import ValidationReport, diff_taxonomies


def _event(name: str, node_id: str = "1:1", props: list[str] | None = None) -> TaxonomyEvent:
    return TaxonomyEvent(
        event_name=name,
        flow="Test",
        description="",
        source_node_id=node_id,
        properties=[EventProperty(name=p, type="string", description="") for p in (props or [])],
    )


def _existing(name: str, node_id: str = "1:1", props: list[str] | None = None) -> dict:
    return {
        "description": "",
        "category": "Test",
        "source": f"figma:node_id:{node_id}",
        "properties": {p: {"type": "string", "description": ""} for p in (props or [])},
    }


def test_empty_diff_when_taxonomies_identical():
    existing = {"home_button_clicked": _existing("home_button_clicked", "1:1", ["screen_name"])}
    current = [_event("home_button_clicked", "1:1", ["screen_name"])]

    report = diff_taxonomies(existing, current)

    assert isinstance(report, ValidationReport)
    assert report.added == []
    assert report.removed == []
    assert report.renamed == []
    assert report.property_changes == []
    assert report.is_clean() is True


def test_detects_added_event():
    existing = {}
    current = [_event("home_button_clicked", "1:1")]

    report = diff_taxonomies(existing, current)

    assert len(report.added) == 1
    assert report.added[0].event_name == "home_button_clicked"
    assert report.is_clean() is False


def test_detects_removed_event():
    existing = {"old_event": _existing("old_event", "9:9")}
    current = []

    report = diff_taxonomies(existing, current)

    assert len(report.removed) == 1
    assert report.removed[0] == "old_event"


def test_detects_renamed_event_by_node_id():
    """Same Figma node, different event name = rename (not add+remove)."""
    existing = {"login_btn_clicked": _existing("login_btn_clicked", "1:5")}
    current = [_event("login_submit_clicked", "1:5")]

    report = diff_taxonomies(existing, current)

    assert report.renamed == [("login_btn_clicked", "login_submit_clicked")]
    assert report.added == []
    assert report.removed == []


def test_detects_property_additions():
    existing = {"signup_form_submitted": _existing("signup_form_submitted", "2:1", ["screen_name"])}
    current = [_event("signup_form_submitted", "2:1", ["screen_name", "is_valid"])]

    report = diff_taxonomies(existing, current)

    assert len(report.property_changes) == 1
    change = report.property_changes[0]
    assert change["event_name"] == "signup_form_submitted"
    assert change["added"] == ["is_valid"]
    assert change["removed"] == []


def test_detects_property_removals():
    existing = {"signup_form_submitted": _existing("signup_form_submitted", "2:1", ["screen_name", "stale_prop"])}
    current = [_event("signup_form_submitted", "2:1", ["screen_name"])]

    report = diff_taxonomies(existing, current)

    assert report.property_changes[0]["removed"] == ["stale_prop"]
    assert report.property_changes[0]["added"] == []
