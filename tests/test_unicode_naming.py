import json
import unicodedata
from pathlib import Path

import pytest
from click.testing import CliRunner

from figma_taxonomy.cli import main
from figma_taxonomy.config import TaxonomyConfig
from figma_taxonomy.extractor import explain_detection, extract_elements, extract_screens
from figma_taxonomy.models import ScreenElement
from figma_taxonomy.taxonomy_engine import _to_snake_case, generate_taxonomy


def _file(labels: list[str], screen: str = "Login") -> dict:
    return {"document": {"id": "0:0", "type": "DOCUMENT", "name": "App", "children": [
        {"id": "1:0", "type": "CANVAS", "name": "Auth", "children": [
            {"id": "1:1", "type": "FRAME", "name": screen, "children": [
                {"id": f"2:{index}", "type": "INSTANCE", "name": "Button/Secondary", "children": [
                    {"id": f"3:{index}", "type": "TEXT", "name": "Label", "characters": label},
                ]} for index, label in enumerate(labels)
            ]},
        ]},
    ]}}


def test_cyrillic_controls_remain_distinct() -> None:
    config = TaxonomyConfig()
    data = _file(["Войти", "Отмена"])
    events = generate_taxonomy(extract_elements(data, config), config)
    assert [(event.event_name, event.source_node_ids) for event in events] == [
        ("login_voyti_clicked", ["2:0"]),
        ("login_otmena_clicked", ["2:1"]),
        ("login_pageview", ["1:1"]),
    ]


@pytest.mark.parametrize(("label", "expected"), [
    ("Ә Ғ Қ Ң Ө Ұ Ү Һ І", "a_g_q_ng_o_u_u_h_i"),
    ("ә ғ қ ң ө ұ ү һ і", "a_g_q_ng_o_u_u_h_i"),
    ("Й Ж Х Ц Ч Ш Щ Ю Я Ё Э Ъ Ь", "y_zh_kh_ts_ch_sh_shch_yu_ya_yo_e"),
    ("й ж х ц ч ш щ ю я ё э ъ ь", "y_zh_kh_ts_ch_sh_shch_yu_ya_yo_e"),
    ("Құпия сөзді өзгерту", "qupiya_sozdi_ozgertu"),
    ("Crème Brûlée", "creme_brulee"),
    ("Cafe\u0301", "cafe"),
])
def test_transliteration(label: str, expected: str) -> None:
    assert _to_snake_case(label) == expected
    element = ScreenElement("1:2", "login", "Button", "button", label, True)
    assert generate_taxonomy([element], TaxonomyConfig())[0].event_name == f"login_{expected}_clicked"


@pytest.mark.parametrize(("screen", "expected"), [
    ("01 - Войти - Dark", "voyti"),
    ("Құпия сөзді өзгерту", "qupiya_sozdi_ozgertu"),
    ("Crème Brûlée", "creme_brulee"),
])
def test_screen_names_use_the_same_transliteration(screen: str, expected: str) -> None:
    config = TaxonomyConfig()
    data = _file(["Save"], screen)
    assert extract_elements(data, config)[0].screen_name == expected
    assert extract_screens(data, config)[0].screen_name == expected


@pytest.mark.parametrize(("text", "expected"), [("Йога", "yoga"), ("Ёж", "yozh"), ("Войти", "voyti")])
def test_canonically_equivalent_labels_and_screens(text: str, expected: str) -> None:
    config = TaxonomyConfig()
    labels = [unicodedata.normalize(form, text) for form in ("NFC", "NFD")]
    for screen in labels:
        data = _file(labels, screen)
        elements = extract_elements(data, config)
        assert {element.screen_name for element in elements} == {expected}
        assert extract_screens(data, config)[0].screen_name == expected
        events = generate_taxonomy(elements, config)
        assert [(event.event_name, event.source_node_ids) for event in events] == [
            (f"{expected}_{expected}_clicked", ["2:0", "2:1"]),
            (f"{expected}_pageview", ["1:1"]),
        ]
        assert explain_detection(data, config, events)["decisions"] == []


@pytest.mark.parametrize("label", ["!!!", "😀", "   ", "漢字", "ъь"])
def test_empty_normalized_text_requires_allowed_fallback(label: str) -> None:
    config = TaxonomyConfig()
    element = ScreenElement("1:234", "login", "Button/Continue", "button", label, True)
    assert generate_taxonomy([element], config)[0].event_name == "login_button_continue_clicked"
    config.naming.element_name.fallback_to_component_name = False
    with pytest.raises(ValueError, match=r"Node 1:234 has no text;.*fallback_to_component_name"):
        generate_taxonomy([element], config)


@pytest.mark.parametrize("use_text", [True, False])
@pytest.mark.parametrize("node_id", ["1:234", ""])
def test_empty_normalized_component_name_uses_node_id(use_text: bool, node_id: str) -> None:
    config = TaxonomyConfig()
    config.naming.element_name.use_text_content = use_text
    element = ScreenElement(node_id, "login", "Component/!!!", "button", "!!!", True)
    if node_id:
        assert generate_taxonomy([element], config)[0].event_name == "login_node_1_234_clicked"
    else:
        with pytest.raises(ValueError, match=r"Control.*component name or node ID"):
            generate_taxonomy([element], config)


def test_icon_only_control_uses_node_id_and_cli_reports_decision(tmp_path: Path) -> None:
    config = TaxonomyConfig()
    data = _file(["★", "Save"])
    control = data["document"]["children"][0]["children"][0]["children"][0]
    control["name"] = "★★"
    control["interactions"] = [{"trigger": {"type": "ON_CLICK"}, "actions": [
        {"type": "NODE", "destinationId": "1:1"},
    ]}]
    events = generate_taxonomy(extract_elements(data, config), config)
    expected_names = ["login_node_2_0_clicked", "login_save_clicked", "login_pageview"]
    assert [event.event_name for event in events] == expected_names
    assert events[0].source_node_ids == ["2:0"]
    expected_decisions = [{
        "reason": "unnamed_control", "node_id": "2:0", "raw_label": "★", "element_name": "node_2_0",
    }]
    assert explain_detection(data, config, events)["decisions"] == expected_decisions

    fixture = tmp_path / "icon.json"
    fixture.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    report_path = tmp_path / "decisions.json"
    output = tmp_path / "output"
    result = CliRunner().invoke(main, [
        "extract", "--fixture", str(fixture), "--format", "json", "--output", str(output),
        "--explain", str(report_path),
    ])
    assert result.exit_code == 0, result.output
    stored_events = json.loads((output / "taxonomy.json").read_text(encoding="utf-8"))["events"]
    assert set(stored_events) == set(expected_names)
    assert stored_events[expected_names[0]]["sources"] == ["figma:node_id:2:0"]
    assert json.loads(report_path.read_text(encoding="utf-8"))["decisions"] == expected_decisions


def test_empty_screen_name_identifies_frame() -> None:
    config = TaxonomyConfig()
    data = _file(["Save"], "!!!")
    for extract in (extract_elements, extract_screens):
        assert [item.screen_name for item in extract(data, config)] == ["frame_1_1"]
    events = generate_taxonomy(extract_elements(data, config), config)
    assert [event.event_name for event in events] == ["frame_1_1_save_clicked", "frame_1_1_pageview"]
    assert explain_detection(data, config, events)["decisions"] == [{
        "reason": "unnamed_screen", "node_id": "1:1", "raw_frame_name": "!!!", "screen_name": "frame_1_1",
    }]


@pytest.mark.parametrize("excluded_page", [True, False])
@pytest.mark.parametrize(("screen", "expected"), [("!!!", ""), ("01 - Old Screen - Dark", "old_screen")])
def test_explanation_does_not_validate_names_of_excluded_screens(
    excluded_page: bool, screen: str, expected: str,
) -> None:
    config = TaxonomyConfig()
    config.detection.include_hidden = False
    data = _file(["Save"], screen)
    page = data["document"]["children"][0]
    if excluded_page:
        page["name"] = "Archive"
    else:
        page["children"][0]["visible"] = False
    events = generate_taxonomy(extract_elements(data, config), config)
    assert events == []
    report = explain_detection(data, config, events)
    assert report["decisions"] == []
    assert {node["screen_name"] for node in report["nodes"] if node["screen_node_id"] == "1:1"} == {expected}


@pytest.mark.parametrize("style", ["snake_case", "camelCase"])
def test_collisions_disambiguate_and_merge_only_matching_labels(style: str) -> None:
    config = TaxonomyConfig()
    config.naming.style = style
    data = _file(["Pay now", "Pay-now", "Pay_now", "  PAY-NOW  "])
    events = generate_taxonomy(extract_elements(data, config), config)
    expected = ["login_pay_now_clicked", "login_pay_now_button_secondary_clicked", "login_pay_now_2_clicked"]
    if style == "camelCase":
        expected = ["loginPayNowClicked", "loginPayNowButtonSecondaryClicked", "loginPayNow2Clicked"]
    assert [event.event_name for event in events[:-1]] == expected
    assert [event.source_node_ids for event in events[:-1]] == [["2:0"], ["2:1", "2:3"], ["2:2"]]
    report = explain_detection(data, config, events)
    assert [decision["reason"] for decision in report["decisions"]] == ["collision", "collision"]
    assert [decision["event_name"] for decision in report["decisions"]] == expected[1:]
    assert report["decisions"][0]["source_labels"] == ["Pay now", "Pay-now"]


def test_same_labels_merge_with_case_and_whitespace_normalized() -> None:
    config = TaxonomyConfig()
    data = _file(["Pay now", "  PAY\tNOW\n"])
    events = generate_taxonomy(extract_elements(data, config), config)
    assert events[0].source_node_ids == ["2:0", "2:1"]
    assert len(events) == 2
    assert explain_detection(data, config, events)["decisions"] == []


def test_component_labels_without_text_must_agree_to_merge() -> None:
    elements = [ScreenElement(f"1:{index}", "login", name, "button", None, True)
                for index, name in enumerate(["Button/Pay now", "Button/Pay-now", "BUTTON/PAY-NOW"])]
    events = generate_taxonomy(elements, TaxonomyConfig())
    assert len(events) == 3
    assert [event.source_node_ids for event in events[:-1]] == [["1:0"], ["1:1", "1:2"]]

    config = TaxonomyConfig()
    config.naming.element_name.use_text_content = False
    data = _file(["Войти", "Отмена"])
    component_names = ["Button/Primary", "Button-Primary"]
    controls = data["document"]["children"][0]["children"][0]["children"]
    for control, name in zip(controls, component_names):
        control["name"] = name
    events = generate_taxonomy(extract_elements(data, config), config)
    assert explain_detection(data, config, events)["decisions"][0]["source_labels"] == component_names


def test_reused_components_merge_in_component_naming_mode() -> None:
    config = TaxonomyConfig()
    config.naming.element_name.use_text_content = False
    data = _file(["Войти", "Отмена"])
    for node in data["document"]["children"][0]["children"][0]["children"]:
        node["name"] = "Button/Primary"
    events = generate_taxonomy(extract_elements(data, config), config)
    assert [(event.event_name, event.source_node_ids) for event in events] == [
        ("login_button_primary_clicked", ["2:0", "2:1"]),
        ("login_pageview", ["1:1"]),
    ]
    assert explain_detection(data, config, events)["decisions"] == []


@pytest.mark.parametrize("second_component", ["Button/Icon", "Button-Icon"])
def test_icon_button_fallback_uses_component_identity(second_component: str) -> None:
    config = TaxonomyConfig()
    elements = [
        ScreenElement("2:0", "login", "Button/Icon", "button", "→", True),
        ScreenElement("2:1", "login", second_component, "button", "←", True),
    ]
    events = generate_taxonomy(elements, config)
    if second_component == "Button/Icon":
        assert [(event.event_name, event.source_node_ids) for event in events[:-1]] == [
            ("login_button_icon_clicked", ["2:0", "2:1"]),
        ]
    else:
        assert [(event.event_name, event.source_node_ids) for event in events[:-1]] == [
            ("login_button_icon_clicked", ["2:0"]),
            ("login_button_icon_2_clicked", ["2:1"]),
        ]


def test_collision_resolution_survives_patterns_and_length_caps() -> None:
    config = TaxonomyConfig()
    config.naming.pattern = "{screen}_{action}"
    config.naming.max_event_length = 7
    data = _file(["Save", "Cancel", "Other"])
    events = generate_taxonomy(extract_elements(data, config), config)
    assert [event.event_name for event in events] == ["login_c", "login_2", "login_3", "login_p"]
    assert all(len(event.event_name) <= 7 for event in events)
    assert explain_detection(data, config, events)["decisions"] == [
        {
            "reason": "collision", "node_id": "2:1", "conflicting_node_id": "2:0",
            "source_labels": ["Save", "Cancel"], "original_event_name": "login_c", "event_name": "login_2",
        },
        {
            "reason": "collision", "node_id": "2:2", "conflicting_node_id": "2:0",
            "source_labels": ["Save", "Other"], "original_event_name": "login_c", "event_name": "login_3",
        },
    ]


def test_cli_reports_label_collision(tmp_path: Path) -> None:
    fixture = tmp_path / "collision.json"
    fixture.write_text(json.dumps(_file(["Оплата", "Oplata"]), ensure_ascii=False), encoding="utf-8")
    report_path = tmp_path / "decisions.json"
    output = tmp_path / "output"
    result = CliRunner().invoke(main, [
        "extract", "--fixture", str(fixture), "--format", "json", "--output", str(output),
        "--explain", str(report_path),
    ])
    assert result.exit_code == 0, result.output
    events = json.loads((output / "taxonomy.json").read_text(encoding="utf-8"))["events"]
    assert len(events) == 3
    decisions = json.loads(report_path.read_text(encoding="utf-8"))["decisions"]
    assert len(decisions) == 1
    assert decisions[0]["reason"] == "collision"
    assert decisions[0]["original_event_name"] == "login_oplata_clicked"
    assert decisions[0]["event_name"] == "login_oplata_button_secondary_clicked"
    assert events[decisions[0]["event_name"]]["sources"] == ["figma:node_id:2:1"]


@pytest.mark.parametrize("command", ["extract", "validate"])
def test_cli_reports_empty_screen_name_cleanly(command: str, tmp_path: Path) -> None:
    fixture = tmp_path / "emoji.json"
    fixture.write_text(json.dumps(_file(["Save"], "🔥")), encoding="utf-8")
    args = [command]
    if command == "validate":
        taxonomy = tmp_path / "taxonomy.json"
        taxonomy.write_text('{"events": {}}', encoding="utf-8")
        args.append(str(taxonomy))
    else:
        output = tmp_path / "output"
        report_path = tmp_path / "decisions.json"
        args.extend(["--format", "json", "--output", str(output), "--explain", str(report_path)])
    result = CliRunner().invoke(main, [*args, "--fixture", str(fixture)])
    assert result.exit_code == 0, result.output
    assert "Traceback" not in result.output
    assert result.exception is None
    expected_names = {"frame_1_1_save_clicked", "frame_1_1_pageview"}
    if command == "extract":
        events = json.loads((output / "taxonomy.json").read_text(encoding="utf-8"))["events"]
        assert set(events) == expected_names
        assert json.loads(report_path.read_text(encoding="utf-8"))["decisions"] == [{
            "reason": "unnamed_screen", "node_id": "1:1", "raw_frame_name": "🔥", "screen_name": "frame_1_1",
        }]
    else:
        assert all(name in result.output for name in expected_names)


def test_banking_fixture_output_is_unchanged() -> None:
    config = TaxonomyConfig()
    fixture = Path(__file__).parent / "fixtures" / "banking_app.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    events = generate_taxonomy(extract_elements(data, config), config, screens=extract_screens(data, config))
    global_properties = [
        ("screen_name", "string", "Screen where event occurred", None),
        ("platform", "string", "", ["ios", "android", "web"]),
        ("app_version", "string", "Application version", None),
    ]
    clicked = [("element_text", "string", "Visible text of the clicked element", None)] + global_properties
    entered = [
        ("field_name", "string", "Name of the input field", None),
        ("is_valid", "boolean", "Whether the input passed validation", None),
    ] + global_properties
    assert len(events) == 21
    assert {
        event.event_name: [(prop.name, prop.type, prop.description, prop.enum_values) for prop in event.properties]
        for event in events
    } == {
        "login_screen_input_email_entered": entered,
        "login_screen_input_password_entered": entered,
        "login_screen_log_in_clicked": clicked,
        "login_screen_forgot_password_clicked": clicked,
        "login_screen_remember_me_toggled": global_properties,
        "home_account_balance_viewed": global_properties,
        "home_transfer_clicked": clicked,
        "home_pay_bills_clicked": clicked,
        "home_accounts_viewed": global_properties,
        "home_cards_viewed": global_properties,
        "home_bottom_nav_clicked": clicked,
        "payment_form_amount_entered": entered,
        "payment_form_select_account_selected": global_properties,
        "payment_form_save_recipient_checked": global_properties,
        "payment_form_send_payment_clicked": clicked,
        "payment_form_interactive_frame_clicked": clicked,
        "payment_success_done_clicked": clicked,
        "home_pageview": global_properties,
        "login_screen_pageview": global_properties,
        "payment_form_pageview": global_properties,
        "payment_success_pageview": global_properties,
    }
