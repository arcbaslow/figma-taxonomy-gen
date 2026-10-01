from pathlib import Path

from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.extractor import extract_elements, extract_screens
from figma_taxonomy.figma_client import load_fixture
from figma_taxonomy.taxonomy_engine import generate_taxonomy

FIXTURE = Path(__file__).parent / "fixtures" / "detection_policy.json"


def test_nested_labels_variants_and_legacy_interactions() -> None:
    config = TaxonomyConfig()
    elements = {e.node_id: e for e in extract_elements(load_fixture(FIXTURE), config)}
    assert elements["1:2"].text_content == "Pay now"
    assert elements["1:2"].variants == ["State=Ready"]
    assert elements["1:9"].has_interaction
    assert elements["1:5"].text_content is None  # Do not borrow a nested button's label.
    assert "1:6" not in elements  # Parent suppression stays the default.
    assert "1:8" in elements  # Preserve legacy hidden-layer behavior by default.
    assert "1:10" not in elements  # Existing decorative exclusions still win.


def test_hidden_subtrees_and_screen_inventory_use_same_policy() -> None:
    config = TaxonomyConfig()
    config.detection.include_hidden = False
    data = load_fixture(FIXTURE)
    assert "1:8" not in {e.node_id for e in extract_elements(data, config)}
    assert "1:22" not in {e.node_id for e in extract_elements(data, config)}
    assert {s.node_id for s in extract_screens(data, config)} == {"1:1"}


def test_nested_controls_are_explicit_and_keep_their_own_sources() -> None:
    config = TaxonomyConfig()
    config.detection.traverse_interactive_children = True
    data = load_fixture(FIXTURE)
    elements = extract_elements(data, config)
    assert "1:6" in {e.node_id for e in elements}
    events = generate_taxonomy(elements, config, screens=extract_screens(data, config))
    details = next(e for e in events if e.event_name == "checkout_details_clicked")
    assert details.source_node_ids == ["1:6"]
