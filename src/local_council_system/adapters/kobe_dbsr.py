from __future__ import annotations

import logging
from datetime import date, datetime
from urllib.parse import urlencode

from local_council_system.adapters.base import MinutesAdapter
from local_council_system.config import SourceConfig
from local_council_system.http_client import PoliteHttpClient
from local_council_system.models import DiscoveryContext, MeetingReference, ParsedMeeting
from local_council_system.parsers.kobe_dbsr import parse_listing_html, parse_meeting_html

logger = logging.getLogger(__name__)


class KobeDbsrAdapter(MinutesAdapter):
    """神戸市会 dbsr Adapter。

    1 Meeting は日・号（例: 令和7年第1回定例市会 第6日）。
    本文だけを対象にし、議事日程・名簿および資料は DISCOVER しない。
    Meeting Identity は検索結果の Id。本文の data-voice_code を Speech Identity にする。
    """

    def __init__(self, config: SourceConfig, http: PoliteHttpClient) -> None:
        self._config = config
        self._http = http

    def discover(self, context: DiscoveryContext) -> list[MeetingReference]:
        since_date = _as_date(context.since)
        until_date = _as_date(context.until)
        years = self._target_years(since_date, until_date)
        references: list[MeetingReference] = []
        for year in years:
            year_since = date(year, 1, 1)
            year_until = date(year, 12, 31)
            if since_date:
                year_since = max(year_since, since_date)
            if until_date:
                year_until = min(year_until, until_date)
            if year_since > year_until:
                continue
            url = self._list_url(year_since, year_until)
            logger.info("discover listing year=%s", year)
            html = self._http.get_text(url)
            references.extend(
                parse_listing_html(
                    html,
                    municipality_code=self._config.municipality_code,
                    base_url=self._config.base_url,
                    since=since_date,
                    until=until_date,
                )
            )
        logger.info("discovered %s meetings", len(references))
        return references

    def fetch(self, reference: MeetingReference) -> str:
        url = reference.fetch_url or reference.url
        logger.info("fetch Id=%s", reference.source_meeting_id)
        return self._http.get_text(url)

    def parse(self, html: str, reference: MeetingReference) -> ParsedMeeting:
        return parse_meeting_html(html, reference)

    def _list_url(self, start: date, end: date) -> str:
        query = {
            "Cabinet": "1",
            "QueryType": "new",
            "Template": "list",
            "TermStart": start.isoformat(),
            "TermEnd": end.isoformat(),
        }
        return f"{self._config.base_url}/100000?{urlencode(query)}"

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
