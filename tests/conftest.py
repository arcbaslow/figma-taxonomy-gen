import json
from pathlib import Path

import pytest


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def banking_app_fixture():
    """Load the banking app Figma API response fixture."""
    with open(FIXTURES_DIR / "banking_app.json") as f:
        return json.load(f)
