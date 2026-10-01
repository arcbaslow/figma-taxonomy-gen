import json
from copy import deepcopy
from pathlib import Path

from click.testing import CliRunner

from figma_taxonomy import extractor
from figma_taxonomy.cli import main
from figma_taxonomy.config import DetectionOverride, TaxonomyConfig
from figma_taxonomy.figma_client import load_fixture
from figma_taxonomy.mcp_tools import extract_taxonomy_tool
from figma_taxonomy.taxonomy_engine import generate_taxonomy

FIXTURE = Path(__file__).parent / "fixtures" / "detection_policy.json"


def test_explanation_covers_all_nodes_and_matches_event_sources() -> None:
    data = load_fixture(FIXTURE)
    original = deepcopy(data)
    config = TaxonomyConfig()
    config.detection.include_hidden = False
    config.detection.overrides = [DetectionOverride(node_id="1:10", type="button")]
    elements = extractor.extract_elements(data, config)
    events = generate_taxonomy(elements, config, screens=extractor.extract_screens(data, config))
    report = extractor.explain_detection(data, config, events)
    nodes = {node["node_id"]: node for node in report["nodes"]}
    assert report["schema_version"] == 1
    def ids(node: dict) -> set[str]:
        return {node["id"]}.union(*(ids(child) for child in node.get("children", [])))
    assert set(nodes) == ids(data["document"])
    assert nodes["1:2"]["event_names"] == ["checkout_pay_now_clicked"]
    assert nodes["1:2"]["variants"] == ["State=Ready"]
    assert nodes["1:2"]["screen_node_id"] == "1:1"
    assert nodes["1:6"]["reason"] == "interactive_ancestor"
    assert nodes["1:8"]["reason"] == "hidden"
    assert nodes["1:22"]["reason"] == "hidden_ancestor"
    assert nodes["1:10"]["reason"] == "override_include"
    assert nodes["1:10"]["matched_rule"] == 0
    assert nodes["2:1"]["reason"] == "excluded_page"
    assert nodes["1:1"]["reason"] == "screen_pageview"
    for event in events:
        for source in event.source_node_ids:
            assert event.event_name in nodes[source]["event_names"]
    assert data == original


def test_mcp_explanation_is_optional_and_does_not_change_events() -> None:
    plain = extract_taxonomy_tool(str(FIXTURE))
    explained = extract_taxonomy_tool(str(FIXTURE), explain=True)
    assert "explanation" not in plain
    assert explained["events"] == plain["events"]
    assert explained["explanation"]["nodes"]


def test_cli_writes_explanation_and_protects_taxonomy_path(tmp_path: Path) -> None:
    output = tmp_path / "output"
    report_path = tmp_path / "explanation.json"
    args = ["extract", "--fixture", str(FIXTURE), "--format", "json", "--output", str(output)]
    result = CliRunner().invoke(main, [*args, "--explain", str(report_path)])
    assert result.exit_code == 0, result.output
    assert json.loads(report_path.read_text(encoding="utf-8"))["nodes"]
    previous = (output / "taxonomy.json").read_bytes()
    conflict = CliRunner().invoke(main, [*args, "--explain", str(output / "taxonomy.json")])
    assert conflict.exit_code != 0 and "different path" in conflict.output
    assert (output / "taxonomy.json").read_bytes() == previous
