from datetime import date, datetime
from pathlib import Path

from local_council_system.adapters.kensakusystem import KensakuSystemAdapter
from local_council_system.adapters.registry import create_adapter
from local_council_system.config import load_source_config
from local_council_system.models import DiscoveryContext, MeetingReference
from local_council_system.parsers.kensakusystem import (
    era_year_label,
    parse_day_links,
    parse_meeting_html,
    parse_session_labels,
)

FIXTURES = Path(__file__).parent / "fixtures" / "adapters" / "kensaku"
CONFIG = Path(__file__).resolve().parents[1] / "config" / "sources" / "342084.yaml"
BASE = "https://www.kensakusystem.jp/fuchu-c"


class KensakuFixtureHttp:
    def __init__(self) -> None:
        self.gets: list[str] = []
        self.posts: list[dict[str, str]] = []

    def get_text(self, url: str, *, cache: bool | None = None) -> str:
        self.gets.append(url)
        if url.rstrip("/").endswith("fuchu-c") or url.endswith("index.html"):
            return (FIXTURES / "index.html").read_text(encoding="utf-8")
        if "See.exe" in url:
            return (FIXTURES / "see.html").read_text(encoding="utf-8")
        if "GetText3.exe" in url and "R070225A" in url:
            return (FIXTURES / "print_all.html").read_text(encoding="utf-8")
        raise AssertionError(f"unexpected GET {url}")

    def post_form(
        self,
        url: str,
        data: dict[str, str],
        extra_headers: dict[str, str] | None = None,
        *,
        encoding: str = "utf-8",
        cache: bool = True,
        accept: str | None = None,
    ) -> str:
        assert encoding == "cp932"
        assert cache is False
        self.posts.append(data)
        depth = data.get("treedepth") or ""
        if depth == "令和 7年":
            return (FIXTURES / "year.html").read_text(encoding="utf-8")
        if "第1回定例会" in depth:
            return (FIXTURES / "session.html").read_text(encoding="utf-8")
        return (FIXTURES / "see.html").read_text(encoding="utf-8")


def test_era_year_label_matches_tree_tabs() -> None:
    assert era_year_label(2025) == "令和 7年"
    assert era_year_label(2019) == "令和元年"
    assert era_year_label(2018) == "平成30年"


def test_kensaku_year_keeps_plenary_skips_committees() -> None:
    html = (FIXTURES / "year.html").read_text(encoding="utf-8")
    found = parse_session_labels(html, "令和 7年")
    assert found == ["令和 7年 第1回定例会 ", "令和 7年 第2回定例会 "]


def test_kensaku_days_parse_file_name_and_issue() -> None:
    html = (FIXTURES / "session.html").read_text(encoding="utf-8")
    found = parse_day_links(
        html,
        municipality_code="342084",
        base_url=BASE,
        session_label="令和 7年 第1回定例会 ",
        year=2025,
    )
    assert [item.source_meeting_id for item in found] == ["R070225A", "R070303A"]
    assert found[0].discovered_date == date(2025, 2, 25)
    assert found[0].issue == 1
    assert found[0].name == "本会議"
    assert found[1].discovered_date == date(2025, 3, 3)
    assert found[1].issue == 2
    assert "fileName=R070225A" in found[0].url


def test_kensaku_print_all_splits_speakers() -> None:
    html = (FIXTURES / "print_all.html").read_text(encoding="utf-8")
    reference = MeetingReference(
        municipality_code="342084",
        source_system="kensakusystem",
        source_meeting_id="R070225A",
        url=f"{BASE}/cgi-bin3/ResultFrame.exe?fileName=R070225A",
        discovered_date=date(2025, 2, 25),
        session="令和 7年 第1回定例会",
        name="本会議",
        issue=1,
    )
    parsed = parse_meeting_html(html, reference)
    assert [speech.source_speech_id for speech in parsed.speeches] == ["1", "2", "3"]
    assert parsed.speeches[0].speaker.name == "本谷宏行"
    assert parsed.speeches[0].speaker.position == "議長"
    assert "開会いたします" in parsed.speeches[0].text
    assert parsed.speeches[1].speaker.name == "小野申人"
    assert parsed.speeches[1].speaker.position == "市長"
    assert parsed.speeches[2].speaker.name == "岡田隆行"
    assert parsed.speeches[2].speaker.position == "議員"


def test_kensaku_discover_and_fetch() -> None:
    config = load_source_config(CONFIG)
    http = KensakuFixtureHttp()
    adapter = KensakuSystemAdapter(config, http)  # type: ignore[arg-type]
    found = adapter.discover(
        DiscoveryContext(
            municipality_code="342084",
            since=datetime(2025, 2, 25),
            until=datetime(2025, 2, 25),
        )
    )
    assert [item.source_meeting_id for item in found] == ["R070225A"]
    assert any(item.get("treedepth") == "令和 7年" for item in http.posts)
    parsed = adapter.parse(adapter.fetch(found[0]), found[0])
    assert parsed.speeches[0].speaker.name == "本谷宏行"
    assert any("GetText3.exe" in url and "PRINT_ALL" in url for url in http.gets)
    assert create_adapter(config, http).__class__ is KensakuSystemAdapter  # type: ignore[arg-type]
