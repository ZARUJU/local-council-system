from __future__ import annotations

import re
from datetime import date
from html import unescape
from typing import Any

from local_council_system.models import MeetingReference, ParsedMeeting, ParsedSpeaker, ParsedSpeech

SOURCE_SYSTEM = "discuss"
PLENARY_NAME = "本会議"
SKIP_TYPE_CODES = {1, 2, 9}  # 目次・名簿・資料
SKIP_KIND_MARKERS = ("資料",)
SCHEDULE_RE = re.compile(
    r"(?P<month>\d{1,2})月(?P<day>\d{1,2})日(?:－|-|—)(?P<issue>\d+)号"
)
MEMBER_TITLE_RE = re.compile(r"^(?P<num>\d+)番（(?P<name>.+?)議員）$")
ROLE_TITLE_RE = re.compile(r"^(?P<position>.+?)（(?P<name>.+?)）$")
SCRIPT_RE = re.compile(r"(?is)<script[^>]*>.*?</script>")
STYLE_RE = re.compile(r"(?is)<style[^>]*>.*?</style>")
TAG_RE = re.compile(r"<[^>]+>")
ZEN_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
ZEN_SPACE_RE = re.compile(r"[ \u3000]+")


def parse_councils_payload(
    payload: dict[str, Any],
    *,
    municipality_code: str,
    tenant_slug: str,
    since: date | None = None,
    until: date | None = None,
) -> list[dict[str, str]]:
    """本会議の council_id と会期名。委員会・資料は除く。"""
    found: list[dict[str, str]] = []
    for block in payload.get("councils") or []:
        for year_block in block.get("view_years") or []:
            year = str(year_block.get("view_year") or "")
            for kind in year_block.get("council_type") or []:
                if not _is_plenary_kind(kind):
                    continue
                for council in kind.get("councils") or []:
                    council_id = str(council.get("council_id") or "")
                    name = _normalize_spaces(str(council.get("name") or ""))
                    if not council_id or not name:
                        continue
                    found.append(
                        {
                            "council_id": council_id,
                            "session": name,
                            "year": year,
                            "kind": str(kind.get("council_type_name2") or PLENARY_NAME),
                        }
                    )
    return found


def parse_schedules_payload(
    payload: dict[str, Any],
    *,
    municipality_code: str,
    tenant_slug: str,
    council_id: str,
    session: str,
    year: int,
    since: date | None = None,
    until: date | None = None,
) -> list[MeetingReference]:
    references: list[MeetingReference] = []
    for item in payload.get("council_schedules") or []:
        schedule_id = str(item.get("schedule_id") or "")
        title = _normalize_spaces(str(item.get("name") or ""))
        if not schedule_id or not title:
            continue
        parsed = SCHEDULE_RE.search(title.translate(ZEN_DIGITS))
        if parsed is None:
            continue
        meeting_date = date(year, int(parsed.group("month")), int(parsed.group("day")))
        if since is not None and meeting_date < since:
            continue
        if until is not None and meeting_date > until:
            continue
        issue = int(parsed.group("issue"))
        source_id = f"{council_id}-{schedule_id}"
        view_url = (
            f"https://ssp.kaigiroku.net/tenant/{tenant_slug}/MinuteView.html"
            f"?council_id={council_id}&schedule_id={schedule_id}"
        )
        references.append(
            MeetingReference(
                municipality_code=municipality_code,
                source_system=SOURCE_SYSTEM,
                source_meeting_id=source_id,
                url=view_url,
                discovered_date=meeting_date,
                title_hint=f"{session} {title}",
                session=session,
                name=PLENARY_NAME,
                issue=issue,
                fetch_url=view_url,
                extra={"council_id": council_id, "schedule_id": schedule_id},
            )
        )
    references.sort(
        key=lambda item: (item.discovered_date or date.min, item.issue or 0, item.source_meeting_id)
    )
    return references


def parse_minute_payload(payload: dict[str, Any], reference: MeetingReference) -> ParsedMeeting:
    if reference.discovered_date is None:
        raise ValueError("MeetingReference.discovered_date is required to parse")
    speeches: list[ParsedSpeech] = []
    order = 0
    for item in payload.get("tenant_minutes") or []:
        try:
            type_code = int(item.get("minute_type_code"))
        except (TypeError, ValueError):
            continue
        if type_code in SKIP_TYPE_CODES:
            continue
        minute_id = str(item.get("minute_id") or "")
        title = _normalize_spaces(str(item.get("title") or ""))
        body = _html_to_text(str(item.get("body") or ""))
        text = _strip_title(body, title)
        if not text:
            continue
        order += 1
        page = item.get("page_no")
        try:
            start_page = int(page) if page not in (None, "") else None
        except (TypeError, ValueError):
            start_page = None
        speeches.append(
            ParsedSpeech(
                source_speech_id=minute_id or None,
                order=order,
                speaker=_speaker_from_title(title),
                text=text,
                start_page=start_page,
                source_url=f"{reference.url}#minute-{minute_id}" if minute_id else reference.url,
            )
        )
    if not speeches:
        raise ValueError(f"no speeches found for {reference.source_meeting_id}")
    return ParsedMeeting(
        source_meeting_id=reference.source_meeting_id,
        session=reference.session,
        name=reference.name or PLENARY_NAME,
        date=reference.discovered_date,
        issue=reference.issue,
        speeches=tuple(speeches),
        source_url=reference.url,
        pdf_url=None,
    )


def _is_plenary_kind(kind: dict[str, Any]) -> bool:
    names = [
        str(kind.get("council_type_name1") or ""),
        str(kind.get("council_type_name2") or ""),
        str(kind.get("council_type_name3") or ""),
    ]
    if any(marker in name for name in names for marker in SKIP_KIND_MARKERS):
        return False
    return names[1] == PLENARY_NAME


def _speaker_from_title(title: str) -> ParsedSpeaker:
    member = MEMBER_TITLE_RE.match(title)
    if member:
        return ParsedSpeaker(name=_person_name(member.group("name")), position="議員")
    role = ROLE_TITLE_RE.match(title)
    if role:
        return ParsedSpeaker(
            name=_person_name(role.group("name")),
            position=_person_name(role.group("position")),
        )
    return ParsedSpeaker(name=_person_name(title) or "（不明）")


def _strip_title(text: str, title: str) -> str:
    text = text.strip()
    if not title:
        return text
    first, _, rest = text.partition("\n")
    compact_first = _normalize_spaces(first.lstrip("◆◎○△"))
    if title in compact_first or compact_first.endswith(title):
        idx = compact_first.find(title)
        after = compact_first[idx + len(title) :].lstrip("　 :：")
        parts = [part for part in (after, rest.strip()) if part]
        return "\n".join(parts) or text
    if title in text:
        _, _, after = text.partition(title)
        return after.lstrip("\u3000 \n")
    return text


def _html_to_text(html: str) -> str:
    html = STYLE_RE.sub("", SCRIPT_RE.sub("", html))
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"(?i)</pre\s*>", "\n", text)
    text = TAG_RE.sub("", text)
    text = unescape(text).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def _normalize_spaces(value: str) -> str:
    return ZEN_SPACE_RE.sub(" ", (value or "").replace("\u3000", " ")).strip()


def _person_name(value: str) -> str:
    return _normalize_spaces(value)
