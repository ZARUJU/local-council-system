from __future__ import annotations

import logging
from datetime import date, datetime

from local_council_system.adapters.base import MinutesAdapter
from local_council_system.config import SourceConfig
from local_council_system.http_client import PoliteHttpClient
from local_council_system.models import DiscoveryContext, MeetingReference, ParsedMeeting
from local_council_system.parsers.kensakusystem import (
    era_year_label,
    extract_session_code,
    parse_day_links,
    parse_meeting_html,
    parse_session_labels,
)

logger = logging.getLogger(__name__)


class KensakuSystemAdapter(MinutesAdapter):
    """kensakusystem.jp の会議録閲覧 Adapter。

    閲覧（See.exe）の年次ツリーから本会議の開催日を列挙し、
    全文表示と同じ GetText3.exe PRINT_ALL を FETCH する。
    Code は閲覧セッションなので Identity に使わず、毎回トップから取り直す。
    """

    def __init__(self, config: SourceConfig, http: PoliteHttpClient) -> None:
        self._config = config
        self._http = http
        self._code: str | None = None

    def discover(self, context: DiscoveryContext) -> list[MeetingReference]:
        since_date = _as_date(context.since)
        until_date = _as_date(context.until)
        code = self._resolve_code()
        references: list[MeetingReference] = []
        seen: set[str] = set()
        for year in self._target_years(since_date, until_date):
            year_label = era_year_label(year)
            year_html = self._post_tree(code, year_label)
            sessions = parse_session_labels(year_html, year_label)
            logger.info("discover kensaku year=%s sessions=%s", year, len(sessions))
            for session_label in sessions:
                session_html = self._post_tree(code, session_label)
                for item in parse_day_links(
                    session_html,
                    municipality_code=self._config.municipality_code,
                    base_url=self._config.base_url,
                    session_label=session_label,
                    year=year,
                    since=since_date,
                    until=until_date,
                ):
                    if item.source_meeting_id in seen:
                        continue
                    seen.add(item.source_meeting_id)
                    references.append(item)
        references.sort(
            key=lambda item: (
                item.discovered_date or date.min,
                item.issue or 0,
                item.source_meeting_id,
            )
        )
        logger.info("discovered %s meetings", len(references))
        return references

    def fetch(self, reference: MeetingReference) -> str:
        file_name = str(reference.extra.get("file_name") or reference.source_meeting_id)
        code = self._resolve_code()
        url = (
            f"{self._config.base_url}/cgi-bin3/GetText3.exe"
            f"?{code}/{file_name}/0/10/1/PRINT_ALL/0/0"
        )
        logger.info("fetch fileName=%s", file_name)
        return self._http.get_text(url)

    def parse(self, html: str, reference: MeetingReference) -> ParsedMeeting:
        return parse_meeting_html(html, reference)

    def _resolve_code(self) -> str:
        if self._code:
            return self._code
        html = self._http.get_text(f"{self._config.base_url}/", cache=False)
        code = extract_session_code(html)
        if not code:
            html = self._http.get_text(f"{self._config.base_url}/index.html", cache=False)
            code = extract_session_code(html)
        if not code:
            raise ValueError("kensakusystem session Code not found on index")
        self._code = code
        self._http.get_text(f"{self._see_url()}?Code={code}", cache=False)
        return code

    def _post_tree(self, code: str, treedepth: str) -> str:
        return self._http.post_form(
            self._see_url(),
            {"Code": code, "treedepth": treedepth, "page": "", "fileName": ""},
            extra_headers={"Referer": f"{self._see_url()}?Code={code}"},
            encoding="cp932",
            cache=False,
            accept="text/html",
        )

    def _see_url(self) -> str:
        return f"{self._config.base_url}/cgi-bin3/See.exe"

    def _target_years(self, since: date | None, until: date | None) -> list[int]:
        today = date.today()
        earliest = self._config.collection.earliest_year
        start_year = since.year if since is not None else earliest
        end_year = until.year if until is not None else today.year
        start_year = max(start_year, earliest)
        end_year = max(end_year, start_year)
        return list(range(start_year, end_year + 1))


def _as_date(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value
