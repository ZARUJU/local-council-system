from datetime import date, datetime
from pathlib import Path

from local_council_system.adapters.kobe_dbsr import KobeDbsrAdapter
from local_council_system.adapters.registry import create_adapter
from local_council_system.config import load_source_config
from local_council_system.http_client import decode_html_bytes
from local_council_system.models import DiscoveryContext, MeetingReference
from local_council_system.parsers.kobe_dbsr import (
    listing_page_hrefs,
    parse_listing_html,
    parse_meeting_html,
)

FIXTURES = Path(__file__).parent / "fixtures" / "adapters" / "dbsr"
BASE = "https://www.pref.hiroshima.dbsr.jp"


def test_pref_listing_keeps_body_and_classic_dates() -> None:
    html = decode_html_bytes((FIXTURES / "pref_list.html").read_bytes())
    references = parse_listing_html(html, municipality_code="340006", base_url=BASE)
    assert [item.source_meeting_id for item in references] == ["2001", "2171"]
    first = references[0]
    assert first.discovered_date == date(2025, 2, 20)
    assert first.name == "本会議"
    assert first.session == "令和７年２月定例会"
    assert first.issue == 1
    later = references[1]
    assert later.discovered_date == date(2025, 12, 22)
    assert later.issue == 5
    assert "DocumentID=2171" in (later.fetch_url or "")


def test_pref_listing_follows_page_hrefs() -> None:
    html = decode_html_bytes((FIXTURES / "pref_list.html").read_bytes())
    hrefs = listing_page_hrefs(html, BASE)
    assert any("Page=2" in url for url in hrefs)
    assert any("/index.php/2222222" in url for url in hrefs)


def test_pref_parse_page_text_voices() -> None:
    html = decode_html_bytes((FIXTURES / "pref_document_2171.html").read_bytes())
    reference = MeetingReference(
        municipality_code="340006",
        source_system="dbsr",
        source_meeting_id="2171",
        url="https://www.pref.hiroshima.dbsr.jp/index.php/9209909?Template=document&VoiceType=all&DocumentID=2171",
        discovered_date=date(2025, 12, 22),
        session="令和７年12月定例会",
        name="本会議",
        issue=5,
        fetch_url="https://www.pref.hiroshima.dbsr.jp/index.php/9209909?Template=document&VoiceType=all&DocumentID=2171",
    )
    parsed = parse_meeting_html(html, reference)
    assert [speech.source_speech_id for speech in parsed.speeches] == ["88001", "88002"]
    assert parsed.speeches[0].speaker.name == "中本隆志"
    assert parsed.speeches[0].speaker.position == "議長"
    assert "これより会議を開きます" in parsed.speeches[0].text
    assert parsed.speeches[0].speaker.name != "1:"
    assert parsed.speeches[1].speaker.name == "藤井敏子"
    assert "質問いたします" in parsed.speeches[1].text


class PrefFixtureHttp:
    def __init__(self) -> None:
        self.list_urls: list[str] = []

    def get_text(self, url: str) -> str:
        if "Template=list" in url or "1502739" in url:
            self.list_urls.append(url)
            if "Page=2" in url:
                return decode_html_bytes((FIXTURES / "pref_list_page2.html").read_bytes())
            return decode_html_bytes((FIXTURES / "pref_list.html").read_bytes())
        if "DocumentID=2171" in url:
            return decode_html_bytes((FIXTURES / "pref_document_2171.html").read_bytes())
        raise AssertionError(f"unexpected URL in fixture HTTP: {url}")


def test_pref_discover_walks_href_pages_and_cabinets() -> None:
    config = load_source_config(
        Path(__file__).resolve().parents[1] / "config" / "sources" / "340006.yaml"
    )
    http = PrefFixtureHttp()
    adapter = KobeDbsrAdapter(config, http)  # type: ignore[arg-type]
    found = adapter.discover(
        DiscoveryContext(
            municipality_code="340006",
            since=datetime(2025, 1, 1),
            until=datetime(2025, 12, 31),
        )
    )
    assert [item.source_meeting_id for item in found] == ["2001", "2100", "2171"]
    assert any("Cabinet=1" in url for url in http.list_urls)
    assert any("Cabinet=2" in url for url in http.list_urls)
    assert any("Page=2" in url and "TermStart=2025-01-01" in url for url in http.list_urls)
    assert create_adapter(config, http).__class__ is KobeDbsrAdapter  # type: ignore[arg-type]


HATS_BASE = "https://www.city.hatsukaichi.hiroshima.dbsr.jp"


def test_hatsukaichi_listing_rewrites_doc_page_and_skips_roster() -> None:
    html = decode_html_bytes((FIXTURES / "hatsukaichi_list.html").read_bytes())
    references = parse_listing_html(html, municipality_code="342131", base_url=HATS_BASE)
    assert [item.source_meeting_id for item in references] == ["1024", "1032"]
    first = references[0]
    assert first.discovered_date == date(2025, 12, 3)
    assert first.issue == 2
    assert first.name == "本会議"
    later = references[1]
    assert later.discovered_date == date(2025, 12, 22)
    assert later.issue == 6
    assert "Template=doc-page" in (later.fetch_url or "")
    assert "VoiceType=all" in (later.fetch_url or "")
    assert "doc-one-frame" not in (later.fetch_url or "")
    hrefs = listing_page_hrefs(html, HATS_BASE)
    assert any("Page=2" in url for url in hrefs)


def test_hatsukaichi_parse_docpage_voices_without_kun() -> None:
    html = decode_html_bytes((FIXTURES / "hatsukaichi_docpage.html").read_bytes())
    reference = MeetingReference(
        municipality_code="342131",
        source_system="dbsr",
        source_meeting_id="1032",
        url="https://www.city.hatsukaichi.hiroshima.dbsr.jp/index.php/1888587?Template=doc-page&VoiceType=all&DocumentID=1032",
        discovered_date=date(2025, 12, 22),
        session="令和７年第４回定例会",
        name="本会議",
        issue=6,
        fetch_url="https://www.city.hatsukaichi.hiroshima.dbsr.jp/index.php/1888587?Template=doc-page&VoiceType=all&DocumentID=1032",
    )
    parsed = parse_meeting_html(html, reference)
    assert [speech.source_speech_id for speech in parsed.speeches] == ["1", "2", "3"]
    assert parsed.speeches[0].speaker.name == "新田茂美"
    assert parsed.speeches[0].speaker.position == "議長"
    assert "おはようございます" in parsed.speeches[0].text
    assert parsed.speeches[1].speaker.name == "三宅洋一"
    assert parsed.speeches[1].speaker.position == "議員"
    assert parsed.speeches[1].text.startswith("議長")


class HatsukaichiFixtureHttp:
    def get_text(self, url: str) -> str:
        if "Template=list" in url:
            return decode_html_bytes((FIXTURES / "hatsukaichi_list.html").read_bytes())
        if "DocumentID=1032" in url:
            assert "Template=doc-page" in url
            assert "VoiceType=all" in url
            return decode_html_bytes((FIXTURES / "hatsukaichi_docpage.html").read_bytes())
        raise AssertionError(f"unexpected URL in fixture HTTP: {url}")


def test_hatsukaichi_fetch_uses_doc_page() -> None:
    config = load_source_config(
        Path(__file__).resolve().parents[1] / "config" / "sources" / "342131.yaml"
    )
    http = HatsukaichiFixtureHttp()
    adapter = KobeDbsrAdapter(config, http)  # type: ignore[arg-type]
    found = adapter.discover(
        DiscoveryContext(
            municipality_code="342131",
            since=datetime(2025, 12, 22),
            until=datetime(2025, 12, 22),
        )
    )
    assert [item.source_meeting_id for item in found] == ["1032"]
    parsed = adapter.parse(adapter.fetch(found[0]), found[0])
    assert parsed.speeches[0].speaker.name == "新田茂美"
    assert create_adapter(config, http).__class__ is KobeDbsrAdapter  # type: ignore[arg-type]
