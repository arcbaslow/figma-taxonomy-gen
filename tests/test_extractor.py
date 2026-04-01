import json
from pathlib import Path

import pytest

from figma_taxonomy.config import load_config
from figma_taxonomy.extractor import extract_elements
from figma_taxonomy.models import ScreenElement


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def banking_app():
    with open(FIXTURES_DIR / "banking_app.json") as f:
        return json.load(f)


@pytest.fixture
def config():
    return load_config(None)


@pytest.fixture
def elements(banking_app, config):
    return extract_elements(banking_app, config)


def test_returns_screen_elements(elements):
    assert len(elements) > 0
    assert all(isinstance(e, ScreenElement) for e in elements)


def test_detects_buttons(elements):
    buttons = [e for e in elements if e.element_type == "button"]
    names = [e.element_name for e in buttons]
    assert "log_in" in names or "Log In" in [e.text_content for e in buttons]
    assert len(buttons) >= 4  # Login, Transfer, Pay Bills, Submit, Done


def test_detects_inputs(elements):
    inputs = [e for e in elements if e.element_type == "input"]
    assert len(inputs) >= 3  # Email, Password, Amount


def test_detects_toggles(elements):
    toggles = [e for e in elements if e.element_type == "toggle"]
    assert len(toggles) >= 1  # RememberMe


def test_detects_tabs(elements):
    tabs = [e for e in elements if e.element_type == "tab"]
    assert len(tabs) >= 2  # Accounts, Cards


def test_detects_dropdowns(elements):
    dropdowns = [e for e in elements if e.element_type == "dropdown"]
    assert len(dropdowns) >= 1  # AccountSelect


def test_detects_checkboxes(elements):
    checkboxes = [e for e in elements if e.element_type == "checkbox"]
    assert len(checkboxes) >= 1  # SaveRecipient


def test_detects_links(elements):
    links = [e for e in elements if e.element_type == "link"]
    assert len(links) >= 1  # ForgotPassword


def test_detects_cards(elements):
    cards = [e for e in elements if e.element_type == "card"]
    assert len(cards) >= 1  # AccountBalance


def test_detects_interactive_frames(elements):
    """Frames with prototype interactions should be detected."""
    interactive = [e for e in elements if e.node_id == "3:18"]
    assert len(interactive) == 1
    assert interactive[0].has_interaction is True


def test_excludes_non_interactive(elements):
    """Dividers, icons, loaders, logos should be excluded."""
    node_ids = {e.node_id for e in elements}
    assert "1:18" not in node_ids  # Divider
    assert "3:22" not in node_ids  # Icon/Checkmark
    assert "2:22" not in node_ids  # Loader


def test_excludes_archive_page(elements):
    """Archive page should be excluded via config."""
    node_ids = {e.node_id for e in elements}
    assert "9:10" not in node_ids  # Button in Archive


def test_collapses_variant_frames(elements):
    """Dark variant of Login screen should not produce duplicate elements."""
    login_buttons = [
        e for e in elements
        if e.screen_name == "login_screen" and e.element_type == "button"
    ]
    # Should have exactly 1 button from login (not 2 from default + dark)
    assert len(login_buttons) == 1


def test_screen_names_cleaned(elements):
    screens = {e.screen_name for e in elements}
    # "01 - Login Screen" → "login_screen"
    assert "login_screen" in screens
    # "Home - Default" → "home"
    assert "home" in screens
    # "Payment Form" → "payment_form"
    assert "payment_form" in screens


def test_preserves_node_ids(elements):
    """Every element should have a Figma node ID for traceability."""
    assert all(e.node_id for e in elements)


def test_extracts_text_content(elements):
    buttons = [e for e in elements if e.element_type == "button"]
    texts = [e.text_content for e in buttons if e.text_content]
    assert "Log In" in texts
    assert "Transfer" in texts


def test_parent_path_populated(elements):
    login_elements = [e for e in elements if e.screen_name == "login_screen"]
    for elem in login_elements:
        assert len(elem.parent_path) >= 2  # page + frame at minimum
        assert "Login" in elem.parent_path
