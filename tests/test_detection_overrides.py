from pathlib import Path

import pytest

from figma_taxonomy.config import load_config
from figma_taxonomy.extractor import extract_elements
from figma_taxonomy.figma_client import load_fixture

FIXTURE = Path(__file__).parent / "fixtures" / "detection_policy.json"


def _config(tmp_path: Path, rules: str, options: str = ""):
    path = tmp_path / "config.yaml"
    path.write_text("detection:\n" + options + "  overrides:\n" + rules, encoding="utf-8")
    return load_config(path)


def test_custom_names_and_icon_ctas_preserve_types_and_ids(tmp_path: Path) -> None:
    config = _config(tmp_path, "    - match: 'acme/*'\n      type: button\n    - node_id: '1:10'\n      type: button\n")
    elements = {e.node_id: e for e in extract_elements(load_fixture(FIXTURE), config)}
    assert elements["1:11"].element_type == "button"
    assert elements["1:10"].element_type == "button"
    assert elements["1:10"].has_interaction


def test_first_matching_rule_wins_and_exclusion_blocks_subtree(tmp_path: Path) -> None:
    config = _config(tmp_path,
        "    - node_id: '1:5'\n      action: exclude\n    - match: '*'\n      type: button\n",
        "  traverse_interactive_children: true\n")
    elements = {e.node_id for e in extract_elements(load_fixture(FIXTURE), config)}
    assert "1:5" not in elements and "1:6" not in elements


def test_include_rule_does_not_override_visibility_policy(tmp_path: Path) -> None:
    config = _config(tmp_path, "    - node_id: '1:8'\n      type: button\n", "  include_hidden: false\n")
    assert "1:8" not in {e.node_id for e in extract_elements(load_fixture(FIXTURE), config)}


@pytest.mark.parametrize("rule", [
    "{match: '*', node_id: '1:1'}", "{type: button}", "{match: '*', action: guess}",
    "{match: '*', type: []}", "{match: '*', extra: true}", "{match: ''}",
])
def test_invalid_override_is_rejected(tmp_path: Path, rule: str) -> None:
    with pytest.raises(ValueError, match="overrides"):
        _config(tmp_path, "    - " + rule + "\n")
