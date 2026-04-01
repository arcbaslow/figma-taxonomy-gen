import json
from pathlib import Path

import pytest

from figma_taxonomy.config import load_config
from figma_taxonomy.extractor import extract_elements
from figma_taxonomy.models import ScreenElement, TaxonomyEvent, EventProperty
from figma_taxonomy.taxonomy_engine import generate_taxonomy


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def config():
    return load_config(None)


@pytest.fixture
def elements():
    with open(FIXTURES_DIR / "banking_app.json") as f:
        figma_file = json.load(f)
    config = load_config(None)
    return extract_elements(figma_file, config)


@pytest.fixture
def taxonomy(elements, config):
    return generate_taxonomy(elements, config)


def test_returns_taxonomy_events(taxonomy):
    assert len(taxonomy) > 0
    assert all(isinstance(e, TaxonomyEvent) for e in taxonomy)


def test_generates_screen_pageview_events(taxonomy):
    """Each unique screen should get a _pageview event."""
    pageviews = [e for e in taxonomy if e.event_name.endswith("_pageview")]
    screen_names = {e.event_name.replace("_pageview", "") for e in pageviews}
    assert "login_screen" in screen_names
    assert "home" in screen_names
    assert "payment_form" in screen_names
    assert "payment_success" in screen_names


def test_button_events_use_clicked_action(taxonomy):
    button_events = [
        e for e in taxonomy
        if "clicked" in e.event_name and not e.event_name.endswith("_pageview")
    ]
    assert len(button_events) >= 1


def test_input_events_use_entered_action(taxonomy):
    input_events = [e for e in taxonomy if "entered" in e.event_name]
    assert len(input_events) >= 1


def test_toggle_events_use_toggled_action(taxonomy):
    toggle_events = [e for e in taxonomy if "toggled" in e.event_name]
    assert len(toggle_events) >= 1


def test_tab_events_use_viewed_action(taxonomy):
    tab_events = [
        e for e in taxonomy
        if "viewed" in e.event_name and not e.event_name.endswith("_pageview")
    ]
    assert len(tab_events) >= 1


def test_dropdown_events_use_selected_action(taxonomy):
    dropdown_events = [e for e in taxonomy if "selected" in e.event_name]
    assert len(dropdown_events) >= 1


def test_checkbox_events_use_checked_action(taxonomy):
    checkbox_events = [e for e in taxonomy if "checked" in e.event_name]
    assert len(checkbox_events) >= 1


def test_event_names_are_snake_case(taxonomy):
    for event in taxonomy:
        assert event.event_name == event.event_name.lower(), f"{event.event_name} is not lowercase"
        assert " " not in event.event_name, f"{event.event_name} has spaces"
        assert event.event_name.replace("_", "").isalnum(), f"{event.event_name} has invalid chars"


def test_event_names_within_length_limit(taxonomy, config):
    for event in taxonomy:
        assert len(event.event_name) <= config.naming.max_event_length


def test_events_have_flow_names(taxonomy):
    flows = {e.flow for e in taxonomy}
    assert "Login" in flows
    assert "Home" in flows
    assert "Payments" in flows


def test_events_have_descriptions(taxonomy):
    for event in taxonomy:
        assert event.description, f"{event.event_name} has no description"


def test_events_have_source_node_ids(taxonomy):
    non_pageview = [e for e in taxonomy if not e.event_name.endswith("_pageview")]
    for event in non_pageview:
        assert event.source_node_id, f"{event.event_name} has no source node ID"


def test_clicked_events_have_element_text_property(taxonomy):
    """Property rule: *_clicked → element_text."""
    clicked = [e for e in taxonomy if e.event_name.endswith("_clicked")]
    for event in clicked:
        prop_names = [p.name for p in event.properties]
        assert "element_text" in prop_names, f"{event.event_name} missing element_text"


def test_entered_events_have_field_properties(taxonomy):
    """Property rule: *_entered → field_name, is_valid."""
    entered = [e for e in taxonomy if e.event_name.endswith("_entered")]
    for event in entered:
        prop_names = [p.name for p in event.properties]
        assert "field_name" in prop_names, f"{event.event_name} missing field_name"
        assert "is_valid" in prop_names, f"{event.event_name} missing is_valid"


def test_global_properties_on_all_events(taxonomy):
    for event in taxonomy:
        prop_names = [p.name for p in event.properties]
        assert "screen_name" in prop_names, f"{event.event_name} missing screen_name"
        assert "platform" in prop_names, f"{event.event_name} missing platform"


def test_no_duplicate_event_names(taxonomy):
    names = [e.event_name for e in taxonomy]
    assert len(names) == len(set(names)), f"Duplicate events: {[n for n in names if names.count(n) > 1]}"


def test_uses_text_content_for_element_name(taxonomy):
    """Button with label 'Transfer' should produce event with 'transfer' in name."""
    transfer_events = [e for e in taxonomy if "transfer" in e.event_name]
    assert len(transfer_events) >= 1


def test_manual_element():
    """Test with a manually created ScreenElement."""
    config = load_config(None)
    elem = ScreenElement(
        node_id="99:1",
        screen_name="settings",
        element_name="BiometricLogin",
        element_type="toggle",
        text_content="Biometric Login",
        has_interaction=False,
        variants=[],
        parent_path=["Settings", "Settings Screen"],
    )
    events = generate_taxonomy([elem], config)
    # Should have 1 toggle event + 1 pageview
    toggle_events = [e for e in events if "toggled" in e.event_name]
    assert len(toggle_events) == 1
    assert "biometric" in toggle_events[0].event_name.lower()
