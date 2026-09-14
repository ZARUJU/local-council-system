from pathlib import Path

import pytest

from local_council_system.http_client import decode_html_bytes

FIXTURES = Path(__file__).parent / "fixtures" / "adapters" / "hiroshima"


@pytest.fixture
def listing_html() -> str:
    return decode_html_bytes((FIXTURES / "act100_plenary_2025.html").read_bytes())


@pytest.fixture
def soumu_listing_html() -> str:
    return decode_html_bytes((FIXTURES / "act100_soumu_2025.html").read_bytes())


@pytest.fixture
def committee_index_html() -> str:
    return decode_html_bytes((FIXTURES / "g08v_views_index.html").read_bytes())


@pytest.fixture
def soumu_asp_html() -> str:
    return decode_html_bytes((FIXTURES / "g08v_views_soumu_2025.html").read_bytes())


@pytest.fixture
def meeting_html() -> str:
    return decode_html_bytes((FIXTURES / "plenary_2025-09-17.html").read_bytes())


@pytest.fixture
def soumu_meeting_html() -> str:
    return decode_html_bytes((FIXTURES / "committee_soumu_2025-07-25.html").read_bytes())
