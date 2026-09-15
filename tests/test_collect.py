from datetime import date, datetime
from json import dumps, loads
from pathlib import Path

from local_council_system.adapters.base import MinutesAdapter
from local_council_system.adapters.hiroshima_voices import HiroshimaVoicesAdapter
from local_council_system.adapters.kobe_dbsr import KobeDbsrAdapter
from local_council_system.adapters.registry import create_adapter
from local_council_system.collectors.service import CollectOptions, CollectorService
from local_council_system.config import load_source_config
from local_council_system.http_client import decode_html_bytes
from local_council_system.models import DiscoveryContext, MeetingReference, ParsedMeeting

FIXTURES = Path(__file__).parent / "fixtures" / "adapters" / "hiroshima"


class FixtureHttp:
    def get_text(self, url: str) -> str:
        if "g08v_views.asp" in url:
            if "Sflg=31" in url:
                return decode_html_bytes((FIXTURES / "g08v_views_soumu_2025.html").read_bytes())
            return decode_html_bytes((FIXTURES / "g08v_views_index.html").read_bytes())
        if "ACT=100" in url or "act=100" in url.lower():
            if "KGTP=3" in url:
                return decode_html_bytes((FIXTURES / "act100_soumu_2025.html").read_bytes())
            return decode_html_bytes((FIXTURES / "act100_plenary_2025.html").read_bytes())
        if "FINO=5145" in url and "ACT=203" in url:
            return decode_html_bytes((FIXTURES / "plenary_2025-09-17.html").read_bytes())
        if "FINO=5137" in url and "ACT=203" in url:
            return decode_html_bytes((FIXTURES / "committee_soumu_2025-07-25.html").read_bytes())
        raise AssertionError(f"unexpected URL in fixture HTTP: {url}")


def test_collect_single_meeting(tmp_path: Path) -> None:
    config = load_source_config(
        Path(__file__).resolve().parents[1] / "config" / "sources" / "341002.yaml"
    )
    adapter = HiroshimaVoicesAdapter(config, FixtureHttp())  # type: ignore[arg-type]
    service = CollectorService(
        config=config,
        adapter=adapter,
        data_root=tmp_path / "canonical",
    )
    result = service.run(
        CollectOptions(
            fino="5145",
            until=date(2025, 12, 31),
            update_state=False,
        )
    )
    assert result.discovered == 1
    assert result.succeeded == 1
    assert result.failed == 0
    assert result.written == 1
    output = tmp_path / "canonical" / "data" / "34" / "341002" / "2025" / "2025-09-17-001.json"
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "山路英男" in text
    assert "394555" in text
    master = tmp_path / "canonical" / "master" / "municipalities.json"
    assert master.exists()
    assert "341002" in master.read_text(encoding="utf-8")
    assert (tmp_path / "canonical" / "schema" / "meeting.schema.json").exists()
    assert (tmp_path / "canonical" / "schema" / "collection-status.schema.json").exists()
    assert not (tmp_path / "canonical" / "status" / "341002.json").exists()


def test_collect_soumu_committee_meeting(tmp_path: Path) -> None:
    config = load_source_config(
        Path(__file__).resolve().parents[1] / "config" / "sources" / "341002.yaml"
    )
    adapter = HiroshimaVoicesAdapter(config, FixtureHttp())  # type: ignore[arg-type]
    service = CollectorService(
        config=config,
        adapter=adapter,
        data_root=tmp_path / "canonical",
    )
    result = service.run(
        CollectOptions(
            fino="5137",
            since=date(2025, 7, 25),
            until=date(2025, 7, 25),
            update_state=False,
        )
    )
    assert result.discovered == 1
    assert result.succeeded == 1
    assert result.failed == 0
    output = tmp_path / "canonical" / "data" / "34" / "341002" / "2025" / "2025-07-25-001.json"
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert '"name": "総務委員会"' in text
    assert "ただいまから、総務委員会を開会いたします。" in text
    assert '"position": "委員長"' in text


class KobeFixtureHttp:
    def __init__(self) -> None:
        self.list_urls: list[str] = []

    def get_text(self, url: str) -> str:
        fixtures = Path(__file__).parent / "fixtures" / "adapters" / "kobe"
        if "Template=list" in url or "/100000" in url:
            self.list_urls.append(url)
            if "Page=2" in url:
                return decode_html_bytes((fixtures / "list_page2.html").read_bytes())
            return decode_html_bytes((fixtures / "list.html").read_bytes())
        if "Id=2020" in url:
            return decode_html_bytes((fixtures / "document_id2020.html").read_bytes())
        raise AssertionError(f"unexpected URL in fixture HTTP: {url}")


def test_collect_kobe_body_document(tmp_path: Path) -> None:
    config = load_source_config(
        Path(__file__).resolve().parents[1] / "config" / "sources" / "281000.yaml"
    )
    adapter = KobeDbsrAdapter(config, KobeFixtureHttp())  # type: ignore[arg-type]
    service = CollectorService(
        config=config,
        adapter=adapter,
        data_root=tmp_path / "canonical",
    )
    result = service.run(
        CollectOptions(
            fino="2020",
            since=date(2025, 3, 28),
            until=date(2025, 3, 28),
            update_state=False,
        )
    )
    assert result.discovered == 1
    assert result.succeeded == 1
    output = tmp_path / "canonical" / "data" / "28" / "281000" / "2025" / "2025-03-28-001.json"
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert '"name": "本会議"' in text
    assert "大野陽平" in text
    assert create_adapter(config, KobeFixtureHttp()).__class__ is KobeDbsrAdapter  # type: ignore[arg-type]


def test_kobe_discover_walks_listing_pages() -> None:
    config = load_source_config(
        Path(__file__).resolve().parents[1] / "config" / "sources" / "281000.yaml"
    )
    http = KobeFixtureHttp()
    adapter = KobeDbsrAdapter(config, http)  # type: ignore[arg-type]
    found = adapter.discover(
        DiscoveryContext(
            municipality_code="281000",
            since=datetime(2025, 1, 1),
            until=datetime(2025, 12, 31),
        )
    )
    assert [item.source_meeting_id for item in found] == [
        "2006",
        "2012",
        "2014",
        "2017",
        "2020",
    ]
    assert any("Page=2" in url for url in http.list_urls)
    assert any("Page=" not in url.split("?", 1)[-1] for url in http.list_urls)


class _OnlyMeetingAdapter(MinutesAdapter):
    def __init__(self, adapter: MinutesAdapter, source_meeting_id: str) -> None:
        self._adapter = adapter
        self._source_meeting_id = source_meeting_id

    def discover(self, context: DiscoveryContext) -> list[MeetingReference]:
        return [
            item
            for item in self._adapter.discover(context)
            if item.source_meeting_id == self._source_meeting_id
        ]

    def fetch(self, reference: MeetingReference) -> str:
        return self._adapter.fetch(reference)

    def parse(self, html: str, reference: MeetingReference) -> ParsedMeeting:
        return self._adapter.parse(html, reference)


def test_collect_success_writes_status_under_data_root(tmp_path: Path) -> None:
    config = load_source_config(
        Path(__file__).resolve().parents[1] / "config" / "sources" / "341002.yaml"
    )
    inner = HiroshimaVoicesAdapter(config, FixtureHttp())  # type: ignore[arg-type]
    data_root = tmp_path / "canonical"
    service = CollectorService(
        config=config,
        adapter=_OnlyMeetingAdapter(inner, "5145"),
        data_root=data_root,
    )
    result = service.run(CollectOptions())
    assert result.sync_success
    assert result.succeeded == 1
    status_path = data_root / "status" / "341002.json"
    assert status_path.exists()
    payload = loads(status_path.read_text(encoding="utf-8"))
    assert payload["schemaVersion"] == "1.0"
    assert payload["municipalityCode"] == "341002"
    assert payload["lastSuccessfulSync"].endswith("Z")
    assert not (tmp_path / "collection-state.json").exists()
    assert not (tmp_path / "var" / "collection-state.json").exists()


def test_collect_failure_does_not_update_status(tmp_path: Path) -> None:
    config = load_source_config(
        Path(__file__).resolve().parents[1] / "config" / "sources" / "341002.yaml"
    )
    data_root = tmp_path / "canonical"
    status_path = data_root / "status" / "341002.json"
    status_path.parent.mkdir(parents=True)
    original = {
        "schemaVersion": "1.0",
        "municipalityCode": "341002",
        "lastSuccessfulSync": "2025-01-01T00:00:00Z",
    }
    status_path.write_text(dumps(original, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    service = CollectorService(
        config=config,
        adapter=HiroshimaVoicesAdapter(config, FixtureHttp()),  # type: ignore[arg-type]
        data_root=data_root,
    )
    result = service.run(CollectOptions())
    assert result.failed >= 1
    assert not result.sync_success
    assert loads(status_path.read_text(encoding="utf-8")) == original
