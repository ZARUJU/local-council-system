from datetime import date

from local_council_system.parsers.hiroshima_voices import (
    parse_committee_sflgs,
    parse_iframe_listing_url,
    parse_listing_html,
)

MINUTES_BASE = "https://hiroshima.gijiroku.com/voices"


def test_discover_skips_table_of_contents(listing_html: str) -> None:
    references = parse_listing_html(
        listing_html,
        municipality_code="341002",
        minutes_base_url=MINUTES_BASE,
        year=2025,
    )
    labels = [item.extra["label"] for item in references]
    assert all("目次" not in label for label in labels)
    assert len(references) == 23


def test_discover_2025_09_17(listing_html: str) -> None:
    references = parse_listing_html(
        listing_html,
        municipality_code="341002",
        minutes_base_url=MINUTES_BASE,
        year=2025,
    )
    target = next(item for item in references if item.source_meeting_id == "5145")
    assert target.discovered_date == date(2025, 9, 17)
    assert target.issue == 2
    assert target.name == "本会議"
    assert target.session == "令和７年第３回９月定例会"
    assert target.source_system == "voices"
    assert target.fetch_url is not None
    assert "ACT=203" in target.fetch_url
    assert "FINO=5145" in target.fetch_url
    assert "HATSUGENMODE=1" in target.fetch_url
    assert target.extra["unid"] == "K_R07091700021"
    assert target.extra["kgno"] == "3346"


def test_discover_soumu_committee_name(soumu_listing_html: str) -> None:
    references = parse_listing_html(
        soumu_listing_html,
        municipality_code="341002",
        minutes_base_url=MINUTES_BASE,
        year=2025,
    )
    assert len(references) == 6
    target = next(item for item in references if item.source_meeting_id == "5137")
    assert target.discovered_date == date(2025, 7, 25)
    assert target.issue == 1
    assert target.name == "総務委員会"
    assert target.session == "令和７年７月２５日"
    assert "ACT=203" in (target.fetch_url or "")
    assert "FINO=5137" in (target.fetch_url or "")


def test_committee_sflgs_skip_aggregates(committee_index_html: str) -> None:
    assert parse_committee_sflgs(committee_index_html, 2025) == [
        "31",
        "32",
        "33",
        "34",
        "35",
        "36",
        "41",
        "55",
        "56",
        "52",
    ]
    assert parse_committee_sflgs(committee_index_html, 2024) == []


def test_iframe_listing_url(soumu_asp_html: str) -> None:
    url = parse_iframe_listing_url(soumu_asp_html, MINUTES_BASE)
    assert url is not None
    assert "ACT=100" in url
    assert "KGTP=3" in url
    assert "TITL=" in url


def test_session_and_name_committee_variants() -> None:
    from local_council_system.parsers.hiroshima_voices import _session_and_name

    assert _session_and_name("令和７年第３回９月定例会") == (
        "令和７年第３回９月定例会",
        "本会議",
    )
    assert _session_and_name("令和７年７月２５日総務委員会") == (
        "令和７年７月２５日",
        "総務委員会",
    )
    assert _session_and_name("令和７年度予算特別委員会") == (
        "令和７年度",
        "予算特別委員会",
    )
    assert _session_and_name("令和６年度決算特別委員会（第１分科会）") == (
        "令和６年度",
        "決算特別委員会（第１分科会）",
    )
    assert _session_and_name("令和７年２月６日大都市税財政・地方創生対策特別委員会") == (
        "令和７年２月６日",
        "大都市税財政・地方創生対策特別委員会",
    )


def test_discover_respects_since(listing_html: str) -> None:
    references = parse_listing_html(
        listing_html,
        municipality_code="341002",
        minutes_base_url=MINUTES_BASE,
        year=2025,
        since=date(2025, 9, 17),
        until=date(2025, 9, 17),
    )
    assert [item.source_meeting_id for item in references] == ["5145"]
