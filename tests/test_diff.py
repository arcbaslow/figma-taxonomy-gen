"""Tests for diffing two stored taxonomy JSON files against each other."""

from __future__ import annotations

from figma_taxonomy.validate import diff_taxonomy_dicts


def _event(name: str, node_id: str = "1:1", props: list[str] | None = None) -> dict:
    return {
        "description": "",
        "category": "Test",
        "source": f"figma:node_id:{node_id}",
        "properties": {p: {"type": "string", "description": ""} for p in (props or [])},
    }


def test_identical_taxonomies_are_clean():
    taxonomy = {"login_clicked": _event("login_clicked", "1:1", ["screen_name"])}
    report = diff_taxonomy_dicts(taxonomy, taxonomy)
    assert report.is_clean()


def test_added_event_in_new():
    old = {}
    new = {"home_viewed": _event("home_viewed", "1:2")}
    report = diff_taxonomy_dicts(old, new)
    assert len(report.added) == 1
    assert report.added[0].event_name == "home_viewed"


def test_removed_event_in_new():
    old = {"gone_clicked": _event("gone_clicked", "9:9")}
    new = {}
    report = diff_taxonomy_dicts(old, new)
    assert report.removed == ["gone_clicked"]


def test_renamed_by_node_id():
    old = {"old_name_clicked": _event("old_name_clicked", "1:5")}
    new = {"new_name_clicked": _event("new_name_clicked", "1:5")}
    report = diff_taxonomy_dicts(old, new)
    assert report.renamed == [("old_name_clicked", "new_name_clicked")]


def test_property_changes():
    old = {"form_submitted": _event("form_submitted", "2:1", ["screen_name"])}
    new = {"form_submitted": _event("form_submitted", "2:1", ["screen_name", "is_valid"])}
    report = diff_taxonomy_dicts(old, new)
    assert report.property_changes[0]["added"] == ["is_valid"]
    assert report.property_changes[0]["removed"] == []
