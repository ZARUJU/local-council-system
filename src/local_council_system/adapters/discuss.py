from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

from local_council_system.adapters.base import MinutesAdapter
from local_council_system.config import SourceConfig
from local_council_system.http_client import PoliteHttpClient
from local_council_system.models import DiscoveryContext, MeetingReference, ParsedMeeting
from local_council_system.parsers.discuss import (
    parse_councils_payload,
    parse_minute_payload,
    parse_schedules_payload,
)

logger = logging.getLogger(__name__)

API_ROOT = "/dnp/search"
APIS = {
    "VIEW_YEARS": "councils/get_view_years",
    "COUNCILS": "councils/index",
    "SCHEDULES": "minutes/get_schedule",
    "MINUTES": "minutes/get_minute",
}


class DiscussAdapter(MinutesAdapter):
    """Discuss（ssp.kaigiroku.net）の閲覧 JSON Adapter。

    議会が案内する閲覧画面が使う一覧・本文だけを POST する。
    検索・統計・ログイン・発言集作成は呼ばない。
    1 Meeting は日程・号（schedule）。本会議のみ。名簿・目次・資料は対象外。
    """

    def __init__(self, config: SourceConfig, http: PoliteHttpClient) -> None:
        if not config.tenant_id or not config.tenant_slug:
            raise ValueError("discuss adapter requires source.tenantId and source.tenantSlug")
        self._config = config
        self._http = http
        self._referer = f"{config.minutes_base_url}/MinuteBrowse.html"

    def discover(self, context: DiscoveryContext) -> list[MeetingReference]:
        since_date = _as_date(context.since)
        until_date = _as_date(context.until)
        years = self._target_years(since_date, until_date)
        references: list[MeetingReference] = []
        seen: set[str] = set()
        for year in years:
            payload = self._api("COUNCILS", {"tenant_id": self._config.tenant_id, "view_years": str(year)})
            councils = parse_councils_payload(
                payload,
                municipality_code=self._config.municipality_code,
                tenant_slug=self._config.tenant_slug or "",
                since=since_date,
                until=until_date,
            )
            logger.info("discover discuss year=%s councils=%s", year, len(councils))
            for council in councils:
                council_id = council["council_id"]
                schedules = self._api(
                    "SCHEDULES",
                    {"tenant_id": self._config.tenant_id, "council_id": council_id},
                )
                for item in parse_schedules_payload(
                    schedules,
                    municipality_code=self._config.municipality_code,
                    tenant_slug=self._config.tenant_slug or "",
                    council_id=council_id,
                    session=council["session"],
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
        council_id = str(reference.extra.get("council_id") or "")
        schedule_id = str(reference.extra.get("schedule_id") or "")
        if not council_id or not schedule_id:
            council_id, _, schedule_id = reference.source_meeting_id.partition("-")
        logger.info("fetch council_id=%s schedule_id=%s", council_id, schedule_id)
        payload = self._api(
            "MINUTES",
            {
                "tenant_id": self._config.tenant_id or "",
                "power_user": "false",
                "council_id": council_id,
                "schedule_id": schedule_id,
            },
        )
        return json.dumps(payload, ensure_ascii=False)

    def parse(self, html: str, reference: MeetingReference) -> ParsedMeeting:
        payload = json.loads(html)
        return parse_minute_payload(payload, reference)

    def _api(self, name: str, data: dict[str, str]) -> dict[str, Any]:
        url = f"{self._config.base_url}{API_ROOT}/{APIS[name]}"
        text = self._http.post_form(
            url,
            data,
            extra_headers={"Referer": self._referer},
        )
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError(f"discuss {name} returned non-object JSON")
        return payload

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
