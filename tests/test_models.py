from figma_taxonomy.models import ScreenElement, TaxonomyEvent, EventProperty


def test_screen_element_creation():
    elem = ScreenElement(
        node_id="1:234",
        screen_name="onboarding_welcome",
        element_name="get_started",
        element_type="button",
        text_content="Get Started",
        has_interaction=True,
        variants=[],
        parent_path=["Onboarding", "01 - Welcome"],
    )
    assert elem.node_id == "1:234"
    assert elem.element_type == "button"
    assert elem.text_content == "Get Started"


def test_event_property_creation():
    prop = EventProperty(
        name="error_description",
        type="string",
        description="Description of the error",
        enum_values=None,
    )
    assert prop.name == "error_description"
    assert prop.enum_values is None


def test_event_property_with_enum():
    prop = EventProperty(
        name="platform",
        type="string",
        description="User platform",
        enum_values=["ios", "android", "web"],
    )
    assert prop.enum_values == ["ios", "android", "web"]


def test_taxonomy_event_creation():
    props = [
        EventProperty(
            name="screen_name",
            type="string",
            description="Screen where event occurred",
            enum_values=None,
        )
    ]
    event = TaxonomyEvent(
        event_name="login_pageview",
        flow="Authentication",
        description="User views login screen",
        properties=props,
        source_node_id="2:100",
    )
    assert event.event_name == "login_pageview"
    assert event.flow == "Authentication"
    assert len(event.properties) == 1
    assert event.source_node_id == "2:100"
