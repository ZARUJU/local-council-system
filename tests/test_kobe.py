from datetime import date
from pathlib import Path

from local_council_system.http_client import decode_html_bytes
from local_council_system.models import MeetingReference
from local_council_system.parsers.kobe_dbsr import (
    listing_page_numbers,
    parse_listing_html,
    parse_meeting_html,
)

FIXTURES = Path(__file__).parent / "fixtures" / "adapters" / "kobe"
BASE = "https://www.city.kobe.hyogo.dbsr.jp"


def _reference() -> MeetingReference:
    return MeetingReference(
        municipality_code="281000",
        source_system="dbsr",
        source_meeting_id="2020",
        url="https://www.city.kobe.hyogo.dbsr.jp/333845?Template=document&Id=2020",
        discovered_date=date(2025, 3, 28),
        session="令和７年第１回定例市会（２月議会）",
        name="本会議",
        issue=6,
        fetch_url="https://www.city.kobe.hyogo.dbsr.jp/333845?Template=document&Id=2020",
    )


def test_kobe_listing_keeps_body_skips_roster_and_attachments() -> None:
    html = decode_html_bytes((FIXTURES / "list.html").read_bytes())
    references = parse_listing_html(html, municipality_code="281000", base_url=BASE)
    titles = [item.title_hint or "" for item in references]
    assert [item.source_meeting_id for item in references] == ["2012", "2014", "2017", "2020"]
    assert all(title.endswith("本文") for title in titles)
    assert all("名簿" not in title for title in titles)
    assert all("資料" not in title for title in titles)
    target = next(item for item in references if item.source_meeting_id == "2020")
    assert target.discovered_date == date(2025, 3, 28)
    assert target.name == "本会議"
    assert target.session == "令和７年第１回定例市会（２月議会）"
    assert target.issue == 6
    assert target.source_system == "dbsr"
    assert "Id=2020" in (target.fetch_url or "")
    assert "/333845" in (target.fetch_url or "")


def test_kobe_listing_page_numbers_from_pager() -> None:
    html = decode_html_bytes((FIXTURES / "list.html").read_bytes())
    assert listing_page_numbers(html) == {1, 2}
    page2 = decode_html_bytes((FIXTURES / "list_page2.html").read_bytes())
    assert listing_page_numbers(page2) == {1, 2}


def test_kobe_listing_second_page_keeps_body() -> None:
    html = decode_html_bytes((FIXTURES / "list_page2.html").read_bytes())
    references = parse_listing_html(html, municipality_code="281000", base_url=BASE)
    assert [item.source_meeting_id for item in references] == ["2006"]
    assert references[0].discovered_date == date(2025, 2, 18)
    assert references[0].name == "本会議"



def test_kobe_parse_2025_03_28_body() -> None:
    html = decode_html_bytes((FIXTURES / "document_id2020.html").read_bytes())
    parsed = parse_meeting_html(html, _reference())
    assert len(parsed.speeches) == 275
    assert parsed.speeches[0].source_speech_id == "1"
    assert parsed.speeches[-1].source_speech_id == "275"
    assert parsed.speeches[0].speaker.name == "坊 やすなが"
    assert parsed.speeches[0].speaker.position == "議長"
    assert "ただいまより本日の会議を開きます" in parsed.speeches[0].text
    assert parsed.speeches[0].source_url == (
        "https://www.city.kobe.hyogo.dbsr.jp/333845?Template=document&Id=2020#all:1"
    )

    oono = parsed.speeches[1]
    assert oono.speaker.name == "大野陽平"
    assert oono.speaker.position == "議員"
    assert oono.source_speech_id == "2"
    assert "自民党の大野陽平です" in oono.text

    mayor = next(speech for speech in parsed.speeches if speech.speaker.position == "市長")
    assert mayor.speaker.name == "久元喜造"
    deputy = next(speech for speech in parsed.speeches if speech.speaker.position == "副市長")
    assert deputy.speaker.name in {"小原一徳", "今西正男"}
    education = next(speech for speech in parsed.speeches if speech.speaker.position == "教育長")
    assert education.speaker.name == "福本 靖"
    bureau = next(speech for speech in parsed.speeches if speech.speaker.position == "交通局長")
    assert bureau.speaker.name == "城南雅一"
    election = next(
        speech for speech in parsed.speeches if speech.speaker.position == "選挙管理委員会事務局長"
    )
    assert election.speaker.name == "長谷英昭"
