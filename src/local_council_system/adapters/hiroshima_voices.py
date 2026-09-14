from __future__ import annotations

import logging
from datetime import date, datetime
from urllib.parse import urlencode

from local_council_system.adapters.base import MinutesAdapter
from local_council_system.config import SourceConfig
from local_council_system.http_client import PoliteHttpClient
from local_council_system.models import DiscoveryContext, MeetingReference, ParsedMeeting
from local_council_system.parsers.hiroshima_voices import (
    listing_is_empty,
    parse_committee_sflgs,
    parse_iframe_listing_url,
    parse_listing_html,
    parse_meeting_html,
)

logger = logging.getLogger(__name__)

# 本会議の閲覧 iframe と同じ CGI 条件。
PLENARY_QUERY = {
    "ACT": "100",
    "KTYP": "0,1,2,3",
    "SORT": "0",
    "KGTP": "1,2",
}


class HiroshimaVoicesAdapter(MinutesAdapter):
    """広島市議会 VOICES Adapter。

    会議の1単位は会期全体ではなく、日程・号（例: 2025-09-17 02号）。
    本文は ACT=203 かつ HATSUGENMODE=1（全発言）を1リクエストで取得する。
    発見対象は本会議と、委員会閲覧画面に載っている個別委員会。
    """

    def __init__(self, config: SourceConfig, http: PoliteHttpClient) -> None:
        self._config = config
        self._http = http

    def discover(self, context: DiscoveryContext) -> list[MeetingReference]:
        since_date = _as_date(context.since)
        until_date = _as_date(context.until)
        years = self._target_years(since_date, until_date)
        references: list[MeetingReference] = []
        committee_index = self._http.get_text(self._committee_index_url())
        for year in years:
            references.extend(self._discover_listing(self._plenary_listing_url(year), year, since_date, until_date))
            for sflg in parse_committee_sflgs(committee_index, year):
                asp_url = self._committee_year_url(sflg, year)
                logger.info("discover committee asp year=%s sflg=%s", year, sflg)
                asp_html = self._http.get_text(asp_url)
                listing_url = parse_iframe_listing_url(asp_html, self._config.minutes_base_url)
                if listing_url is None:
                    logger.warning("no ACT=100 iframe year=%s sflg=%s", year, sflg)
                    continue
                references.extend(self._discover_listing(listing_url, year, since_date, until_date))
        references = _dedupe_references(references)
        logger.info("discovered %s meetings", len(references))
        return references

    def fetch(self, reference: MeetingReference) -> str:
        url = reference.fetch_url or reference.url
        logger.info("fetch FINO=%s", reference.source_meeting_id)
        return self._http.get_text(url)

    def parse(self, html: str, reference: MeetingReference) -> ParsedMeeting:
        return parse_meeting_html(html, reference)

    def _discover_listing(
        self,
        url: str,
        year: int,
        since_date: date | None,
        until_date: date | None,
    ) -> list[MeetingReference]:
        logger.info("discover listing year=%s url=%s", year, url)
        html = self._http.get_text(url)
        if listing_is_empty(html):
            logger.info("empty listing year=%s", year)
            return []
        return parse_listing_html(
            html,
            municipality_code=self._config.municipality_code,
            minutes_base_url=self._config.minutes_base_url,
            year=year,
            since=since_date,
            until=until_date,
        )

    def _plenary_listing_url(self, year: int) -> str:
        query = {
            **PLENARY_QUERY,
            "FYY": str(year),
            "FMM": "",
            "FDD": "",
            "TYY": str(year),
            "TMM": "",
            "TDD": "",
        }
        return f"{self._config.minutes_base_url}/cgi/voiweb.exe?{urlencode(query, encoding='cp932')}"

    def _committee_index_url(self) -> str:
        return f"{self._config.minutes_base_url}/g08v_views.asp"

    def _committee_year_url(self, sflg: str, year: int) -> str:
        return (
            f"{self._config.minutes_base_url}/g08v_views.asp"
            f"?Sflg={sflg}&FYY={year}&TYY={year}"
        )

    def _target_years(self, since: date | None, until: date | None) -> list[int]:
        today = date.today()
        earliest = self._config.collection.earliest_year
        start_year = since.year if since is not None else earliest
        end_year = until.year if until is not None else today.year
        start_year = max(start_year, earliest)
        end_year = max(end_year, start_year)
        return list(range(start_year, end_year + 1))


def _dedupe_references(references: list[MeetingReference]) -> list[MeetingReference]:
    seen: set[str] = set()
    unique: list[MeetingReference] = []
    for reference in references:
        if reference.source_meeting_id in seen:
            continue
        seen.add(reference.source_meeting_id)
        unique.append(reference)
    unique.sort(
        key=lambda item: (
            item.discovered_date or date.min,
            item.name or "",
            item.issue or 0,
            item.source_meeting_id,
        )
    )
    return unique


def _as_date(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value
