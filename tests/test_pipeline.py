from datetime import date
from json import loads
from pathlib import Path

from fastapi.testclient import TestClient

from local_council_system.adapters.hiroshima_voices import HiroshimaVoicesAdapter
from local_council_system.adapters.kobe_dbsr import KobeDbsrAdapter
from local_council_system.api.app import create_app
from local_council_system.collectors.service import CollectOptions, CollectorService
from local_council_system.config import load_source_config
from local_council_system.db.builder import build_search_database
from local_council_system.exporters.json_exporter import dumps_canonical
from local_council_system.http_client import decode_html_bytes
from local_council_system.models import MeetingReference
from local_council_system.normalizers.canonical import to_canonical
from local_council_system.parsers.hiroshima_voices import parse_meeting_html
from local_council_system.validators.meeting import validate_meeting
from local_council_system.validators.schema import validate_meeting_payload

from test_collect import FixtureHttp, KobeFixtureHttp

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures" / "adapters" / "hiroshima"


def test_canonical_json_matches_schema() -> None:
    html = decode_html_bytes((FIXTURES / "plenary_2025-09-17.html").read_bytes())
    reference = MeetingReference(
        municipality_code="341002",
        source_system="voices",
        source_meeting_id="5145",
        url="https://hiroshima.gijiroku.com/voices/cgi/voiweb.exe?ACT=200&FINO=5145",
        discovered_date=date(2025, 9, 17),
        session="令和７年第３回９月定例会",
        name="本会議",
        issue=2,
        fetch_url="https://hiroshima.gijiroku.com/voices/cgi/voiweb.exe?ACT=203&FINO=5145",
    )
    parsed = parse_meeting_html(html, reference)
    canonical = to_canonical(parsed, municipality_code="341002", source_system="voices")
    validate_meeting(canonical)
    validate_meeting_payload(loads(dumps_canonical(canonical)))


def test_pipeline_hiroshima_and_kobe_to_speech_api(tmp_path: Path) -> None:
    data_root = tmp_path / "canonical"
    _collect_hiroshima(data_root)
    _collect_kobe(data_root)
    junk = data_root / "status" / "not-a-meeting.json"
    junk.parent.mkdir(parents=True, exist_ok=True)
    junk.write_text('{"schemaVersion": "1.0", "not": "a meeting"}\n', encoding="utf-8")
    database = tmp_path / "search.sqlite"
    result = build_search_database(data_root, database)
    assert result.municipalities == 2
    assert result.meetings == 2
    assert result.speeches > 100

    client = TestClient(create_app(database))
    hiroshima = client.get("/api/speech", params={"any": "一般質問", "municipalityCode": "341002"})
    assert hiroshima.status_code == 200
    body = hiroshima.json()
    assert body["numberOfRecords"] >= 1
    assert body["speechRecord"][0]["municipality"] == "広島市"
    assert "一般質問" in body["speechRecord"][0]["speech"]

    kobe = client.get("/api/speech", params={"any": "学校給食", "municipalityCode": "281000"})
    assert kobe.status_code == 200
    kobe_body = kobe.json()
    assert kobe_body["numberOfRecords"] >= 1
    assert kobe_body["speechRecord"][0]["municipality"] == "神戸市"
    assert "学校給食" in kobe_body["speechRecord"][0]["speech"]

    empty = client.get("/api/speech", params={"any": "存在しない検索語xyz", "municipalityCode": "341002"})
    assert empty.status_code == 200
    assert empty.json()["numberOfRecords"] == 0
    assert empty.json()["speechRecord"] == []

    invalid = client.get("/api/speech")
    assert invalid.status_code == 400

    meeting = client.get("/api/meeting", params={"meetingID": body["speechRecord"][0]["meetingID"]})
    assert meeting.status_code == 200
    meeting_body = meeting.json()
    assert meeting_body["numberOfRecords"] == 1
    assert len(meeting_body["meetingRecord"][0]["speechRecord"]) == 145


def _collect_hiroshima(data_root: Path) -> None:
    config = load_source_config(ROOT / "config" / "sources" / "341002.yaml")
    service = CollectorService(
        config=config,
        adapter=HiroshimaVoicesAdapter(config, FixtureHttp()),  # type: ignore[arg-type]
        data_root=data_root,
    )
    result = service.run(
        CollectOptions(
            fino="5145",
            since=date(2025, 9, 17),
            until=date(2025, 9, 17),
            update_state=False,
        )
    )
    assert result.succeeded == 1


def _collect_kobe(data_root: Path) -> None:
    config = load_source_config(ROOT / "config" / "sources" / "281000.yaml")
    service = CollectorService(
        config=config,
        adapter=KobeDbsrAdapter(config, KobeFixtureHttp()),  # type: ignore[arg-type]
        data_root=data_root,
    )
    result = service.run(
        CollectOptions(
            fino="2020",
            since=date(2025, 3, 28),
            until=date(2025, 3, 28),
            update_state=False,
        )
    )
    assert result.succeeded == 1
