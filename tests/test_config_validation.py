"""Configuration failures are actionable and never silently change meaning."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from figma_taxonomy.cli import main
from figma_taxonomy.config import TaxonomyConfig, load_config
from figma_taxonomy.models import ScreenElement
from figma_taxonomy.taxonomy_engine import generate_taxonomy


@pytest.mark.parametrize("yaml,match", [
    ("[]", "mapping"), ("naming: []", "naming"), ("unknown: true", "unknown"),
    ("naming:\n  max_event_length: true", "max_event_length"),
    ("naming:\n  max_event_length: 0", "max_event_length"),
    ("naming:\n  style: kebab", "style"),
    ("naming:\n  pattern: '{missing}'", "pattern"),
    ("naming:\n  screen_name:\n    max_depth: 3", "max_depth"),
    ("output:\n  formats: [pdf]", "formats"), ("output:\n  formats: []", "formats"),
    ("ai:\n  enabled: 'false'", "enabled"),
    ("global_properties:\n  - name: p\n    enum: nope", "enum"),
    ("property_rules:\n  - match: '*'", "add"), ("app: [", "YAML"),
])
def test_invalid_config_reports_field(tmp_path: Path, yaml: str, match: str) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(yaml, encoding="utf-8")
    with pytest.raises(ValueError, match=match):
        load_config(path)


def test_defaults_do_not_share_nested_property_lists() -> None:
    first, second = TaxonomyConfig(), TaxonomyConfig()
    first.global_properties[1]["enum"].append("new")
    first.property_rules[0]["add"][0]["name"] = "changed"
    assert "new" not in second.global_properties[1]["enum"]
    assert second.property_rules[0]["add"][0]["name"] == "element_text"


def test_disabled_component_fallback_preserves_node_in_error() -> None:
    config = TaxonomyConfig()
    config.naming.element_name.fallback_to_component_name = False
    element = ScreenElement("1:2", "home", "Button", "button", None, False)
    with pytest.raises(ValueError, match="1:2"):
        generate_taxonomy([element], config)


def test_config_directory_and_cli_override(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    configured = tmp_path / "configured"
    config.write_text(f"app:\n  name: Счёт\noutput:\n  directory: '{configured.as_posix()}'\n  formats: [json]\n", encoding="utf-8")
    fixture = Path(__file__).parent / "fixtures" / "banking_app.json"
    args = ["extract", "--fixture", str(fixture), "--config", str(config)]
    first = CliRunner().invoke(main, args)
    assert first.exit_code == 0, first.output
    assert (configured / "taxonomy.json").exists()
    override = tmp_path / "override"
    second = CliRunner().invoke(main, [*args, "--output", str(override)])
    assert second.exit_code == 0 and (override / "taxonomy.json").exists()


def test_cli_config_error_is_readable(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text("naming: []", encoding="utf-8")
    fixture = Path(__file__).parent / "fixtures" / "banking_app.json"
    result = CliRunner().invoke(main, ["extract", "--fixture", str(fixture), "--config", str(path)])
    assert result.exit_code == 1 and "Error:" in result.output and "naming" in result.output
