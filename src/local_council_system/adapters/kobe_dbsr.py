from __future__ import annotations

import logging
from datetime import date, datetime
from urllib.parse import urlencode

from local_council_system.adapters.base import MinutesAdapter
from local_council_system.config import SourceConfig
from local_council_system.http_client import PoliteHttpClient
from local_council_system.models import DiscoveryContext, MeetingReference, ParsedMeeting
from local_council_system.parsers.kobe_dbsr import (
    listing_page_hrefs_by_page,
    listing_page_numbers,
    parse_listing_html,
    parse_meeting_html,
    rewrite_document_fetch_url,
)

logger = logging.getLogger(__name__)

MAX_LIST_PAGES = 100


class KobeDbsrAdapter(MinutesAdapter):
    """dbsr Adapter（神戸市会、広島県議会など）。

    1 Meeting は日・号。本文だけを対象にし、議事日程・名簿および資料は DISCOVER しない。
    Meeting Identity は検索結果の Id または DocumentID。
    一覧パス・QueryType・Cabinet は yaml の source 節で変える。
    """

    def __init__(self, config: SourceConfig, http: PoliteHttpClient) -> None:
        self._config = config
        self._http = http

    def discover(self, context: DiscoveryContext) -> list[MeetingReference]:
        since_date = _as_date(context.since)
        until_date = _as_date(context.until)
        years = self._target_years(since_date, until_date)
        references: list[MeetingReference] = []
        seen_ids: set[str] = set()
        for year in years:
            year_since = date(year, 1, 1)
            year_until = date(year, 12, 31)
            if since_date:
                year_since = max(year_since, since_date)
            if until_date:
                year_until = min(year_until, until_date)
            if year_since > year_until:
                continue
            for cabinet in self._config.cabinets:
                first_url = self._list_url(year_since, year_until, page=1, cabinet=cabinet)
                to_fetch_pages: dict[int, str] = {1: first_url}
                fetched_pages: set[int] = set()
                while to_fetch_pages:
                    page = min(to_fetch_pages)
                    url = to_fetch_pages.pop(page)
                    if page in fetched_pages:
                        continue
                    if len(fetched_pages) >= MAX_LIST_PAGES:
                        logger.warning(
                            "listing page cap year=%s cabinet=%s cap=%s",
                            year,
                            cabinet,
                            MAX_LIST_PAGES,
                        )
                        break
                    fetched_pages.add(page)
                    logger.info(
                        "discover listing year=%s cabinet=%s page=%s",
                        year,
                        cabinet,
                        page,
                    )
                    html = self._http.get_text(url)
                    for item in parse_listing_html(
                        html,
                        municipality_code=self._config.municipality_code,
                        base_url=self._config.base_url,
                        since=since_date,
                        until=until_date,
                    ):
                        if item.source_meeting_id in seen_ids:
                            continue
                        seen_ids.add(item.source_meeting_id)
                        references.append(item)
                    hrefs = listing_page_hrefs_by_page(html, self._config.base_url)
                    if hrefs:
                        for href_page, href_url in hrefs.items():
                            if href_page in fetched_pages or href_page in to_fetch_pages:
                                continue
                            to_fetch_pages[href_page] = href_url
                    else:
                        for href_page in listing_page_numbers(html):
                            if href_page in fetched_pages or href_page in to_fetch_pages:
                                continue
                            to_fetch_pages[href_page] = self._list_url(
                                year_since, year_until, page=href_page, cabinet=cabinet
                            )
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
        url = rewrite_document_fetch_url(reference.fetch_url or reference.url)
        logger.info("fetch Id=%s", reference.source_meeting_id)
        return self._http.get_text(url)

    def parse(self, html: str, reference: MeetingReference) -> ParsedMeeting:
        return parse_meeting_html(html, reference)

    def _list_url(self, start: date, end: date, page: int = 1, cabinet: int | None = None) -> str:
        query = {
            "Cabinet": str(self._config.cabinets[0] if cabinet is None else cabinet),
            "QueryType": self._config.query_type,
            "Template": "list",
            "TermStart": start.isoformat(),
            "TermEnd": end.isoformat(),
        }
        if page > 1:
            query["Page"] = str(page)
        path = self._config.listing_path
        return f"{self._config.base_url}{path}?{urlencode(query)}"

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
