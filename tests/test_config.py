import textwrap
from pathlib import Path

from figma_taxonomy.config import TaxonomyConfig, load_config


def test_load_default_config():
    """Loading config without a file returns sensible defaults."""
    config = load_config(None)
    assert config.naming.style == "snake_case"
    assert config.naming.actions["button"] == "clicked"
    assert config.naming.actions["input"] == "entered"
    assert config.naming.actions["screen"] == "pageview"
    assert config.naming.max_event_length == 64


def test_load_config_from_yaml(tmp_path):
    """Loading a YAML file overrides defaults."""
    yaml_content = textwrap.dedent("""\
        app:
          type: ecommerce
          name: "TestShop"
        naming:
          style: camelCase
          actions:
            button: "tapped"
    """)
    config_file = tmp_path / "test.yaml"
    config_file.write_text(yaml_content)

    config = load_config(config_file)
    assert config.app.name == "TestShop"
    assert config.app.type == "ecommerce"
    assert config.naming.style == "camelCase"
    assert config.naming.actions["button"] == "tapped"
    # Non-overridden defaults still present
    assert config.naming.actions["input"] == "entered"


def test_config_screen_name_settings():
    config = load_config(None)
    assert config.naming.screen_name.strip_prefixes is True
    assert "- Default" in config.naming.screen_name.strip_suffixes


def test_config_global_properties():
    config = load_config(None)
    names = [p["name"] for p in config.global_properties]
    assert "screen_name" in names
    assert "platform" in names


def test_config_property_rules():
    config = load_config(None)
    fail_rule = next(r for r in config.property_rules if r["match"] == "*_fail")
    prop_names = [p["name"] for p in fail_rule["add"]]
    assert "error_description" in prop_names


def test_config_output_defaults():
    config = load_config(None)
    assert "excel" in config.output.formats
    assert "csv" in config.output.formats
    assert "json" in config.output.formats
    assert "markdown" in config.output.formats


def test_config_exclude_pages():
    config = load_config(None)
    assert "Archive" in config.figma.exclude_pages
