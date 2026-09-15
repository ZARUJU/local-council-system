from datetime import date, datetime
from pathlib import Path

from local_council_system.adapters.discuss import DiscussAdapter
from local_council_system.adapters.registry import create_adapter
from local_council_system.collectors.service import CollectOptions, CollectorService
from local_council_system.config import load_source_config
from local_council_system.models import DiscoveryContext, MeetingReference
from local_council_system.parsers.discuss import (
    parse_councils_payload,
    parse_minute_payload,
    parse_schedules_payload,
)

FIXTURES = Path(__file__).parent / "fixtures" / "adapters" / "discuss"
CONFIG = Path(__file__).resolve().parents[1] / "config" / "sources" / "342025.yaml"


def _payload(name: str) -> dict:
    import json

    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class DiscussFixtureHttp:
    def __init__(self) -> None:
        self.posts: list[str] = []

    def post_form(self, url: str, data: dict[str, str], extra_headers: dict[str, str] | None = None) -> str:
        self.posts.append(url)
        if "councils/index" in url:
            return (FIXTURES / "kure_councils_2025.json").read_text(encoding="utf-8")
        if "minutes/get_schedule" in url:
            if data.get("council_id") != "1243":
                return '{"council_schedules": []}'
            return (FIXTURES / "kure_schedules_1243.json").read_text(encoding="utf-8")
        if "minutes/get_minute" in url:
            return (FIXTURES / "kure_minute_1243_4.json").read_text(encoding="utf-8")
        raise AssertionError(f"unexpected POST {url}")


def test_discuss_councils_keep_plenary_skip_committee_and_docs() -> None:
    found = parse_councils_payload(
        _payload("kure_councils_2025.json"),
        municipality_code="342025",
        tenant_slug="kure",
    )
    assert [item["council_id"] for item in found] == ["1243", "1267", "1280", "1291"]
    assert all(item["kind"] == "本会議" for item in found)


def test_discuss_schedules_parse_date_and_issue() -> None:
    found = parse_schedules_payload(
        _payload("kure_schedules_1243.json"),
        municipality_code="342025",
        tenant_slug="kure",
        council_id="1243",
        session="令和７年第１回３月定例会",
        year=2025,
    )
    assert found[0].source_meeting_id == "1243-2"
    assert found[0].discovered_date == date(2025, 2, 21)
    assert found[0].issue == 1
    assert found[0].name == "本会議"
    target = next(item for item in found if item.source_meeting_id == "1243-4")
    assert target.discovered_date == date(2025, 3, 3)
    assert target.issue == 3
    assert "MinuteView.html" in target.url
    assert "council_id=1243" in target.url
    assert "schedule_id=4" in target.url


def test_discuss_minutes_skip_roster_keep_speeches() -> None:
    reference = MeetingReference(
        municipality_code="342025",
        source_system="discuss",
        source_meeting_id="1243-4",
        url="https://ssp.kaigiroku.net/tenant/kure/MinuteView.html?council_id=1243&schedule_id=4",
        discovered_date=date(2025, 3, 3),
        session="令和７年第１回３月定例会",
        name="本会議",
        issue=3,
        extra={"council_id": "1243", "schedule_id": "4"},
    )
    parsed = parse_minute_payload(_payload("kure_minute_1243_4.json"), reference)
    ids = [speech.source_speech_id for speech in parsed.speeches]
    assert "257" not in ids
    assert parsed.speeches[0].source_speech_id == "259"
    assert parsed.speeches[0].speaker.name == "中田光政"
    assert parsed.speeches[0].speaker.position == "議長"
    assert "これより本日の会議を開きます" in parsed.speeches[0].text
    assert "議長（中田光政）" not in parsed.speeches[0].text
    member = next(speech for speech in parsed.speeches if speech.source_speech_id == "262")
    assert member.speaker.name == "定森健次朗"
    assert member.speaker.position == "議員"
    assert "皆さんおはようございます" in member.text
    mayor = next(speech for speech in parsed.speeches if speech.source_speech_id == "264")
    assert mayor.speaker.name == "新原芳明"
    assert mayor.speaker.position == "市長"


def test_discuss_discover_and_collect(tmp_path: Path) -> None:
    config = load_source_config(CONFIG)
    http = DiscussFixtureHttp()
    adapter = DiscussAdapter(config, http)  # type: ignore[arg-type]
    found = adapter.discover(
        DiscoveryContext(
            municipality_code="342025",
            since=datetime(2025, 3, 3),
            until=datetime(2025, 3, 3),
        )
    )
    assert [item.source_meeting_id for item in found] == ["1243-4"]
    assert any("councils/index" in url for url in http.posts)
    assert any("minutes/get_schedule" in url for url in http.posts)
    assert create_adapter(config, http).__class__ is DiscussAdapter  # type: ignore[arg-type]

    service = CollectorService(config=config, adapter=adapter, data_root=tmp_path / "canonical")
    result = service.run(
        CollectOptions(
            fino="1243-4",
            since=date(2025, 3, 3),
            until=date(2025, 3, 3),
            update_state=False,
        )
    )
    assert result.discovered == 1
    assert result.succeeded == 1
    output = tmp_path / "canonical" / "data" / "34" / "342025" / "2025" / "2025-03-03-001.json"
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert '"name": "本会議"' in text
    assert "定森健次朗" in text
    assert "262" in text
