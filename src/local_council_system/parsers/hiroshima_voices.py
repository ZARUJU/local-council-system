from __future__ import annotations

import re
from datetime import date
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

from local_council_system.http_client import decode_html_bytes
from local_council_system.models import MeetingReference, ParsedMeeting, ParsedSpeaker, ParsedSpeech

SOURCE_SYSTEM = "voices"
PLENARY_NAME = "本会議"

ROW_RE = re.compile(
    r"(?P<session>令和[^,<]+),"
    r"<A\s+HREF=\"javascript:;[^\"]*\"[^>]*onClick=\"winopen\('(?P<href>[^']+)'\);\">"
    r"(?P<label>[^<]+)</A>",
    re.IGNORECASE,
)

DATE_LABEL_RE = re.compile(r"^(?P<month>\d{1,2})月(?P<day>\d{1,2})日-(?P<rest>.+)$")
ISSUE_RE = re.compile(r"^(?P<issue>\d+)号$")
HUID_SPLIT_RE = re.compile(r'<A\s+NAME="(HUID\d+)"></A>', re.IGNORECASE)
SCRIPT_RE = re.compile(r"(?is)<script[^>]*>.*?</script>")
STYLE_RE = re.compile(r"(?is)<style[^>]*>.*?</style>")
MEMBER_RE = re.compile(
    r"^(?P<num>\d+)番（(?P<name>.+?)議員）(?P<text>.*)$",
    re.DOTALL,
)
# 本会議は「氏名　役職　　本文」（役職のあと全角空白2つ以上）。
# 委員会は「氏名　役職」だけで本文が次行、という行が多い。
CHAIR_OR_EXEC_RE = re.compile(
    r"^(?P<name>\S+)　+(?P<position>[^\s　。]{1,40})"
    r"(?:　{2,}[ 　]*(?P<inline>.*)|[　 ]*)$",
    re.DOTALL,
)
# 会期側は「…日」または「…年度」。名称は委員会（分科会があればそれも含む）。
COMMITTEE_NAME_RE = re.compile(
    r"^(?P<session>.*?(?:年度|日))(?P<name>.+委員会(?:（第[^）]+分科会）)?)$"
)
NAME_THEN_TEXT_RE = re.compile(
    r"^(?P<name>\S+)　+(?P<text>.*)$",
    re.DOTALL,
)
HEADER_NAME = "（会議録冒頭）"
# 常任・特別の「すべて表示」。個別委員会と重複するため DISCOVER しない。
AGGREGATE_SFLG = frozenset({"30", "50"})
COMMITTEE_YEAR_SFLG_RE = re.compile(
    r"g08v_views\.asp\?Sflg=(\d+)(?:&|&amp;)FYY=(\d{4})",
    re.IGNORECASE,
)
IFRAME_SRC_RE = re.compile(r"<iframe[^>]+src=\"([^\"]+)\"", re.IGNORECASE)
EMPTY_LISTING_MARKERS = ("該当する発言は存在しません",)


def parse_listing_html(
    html: str,
    *,
    municipality_code: str,
    minutes_base_url: str,
    year: int,
    since: date | None = None,
    until: date | None = None,
    skip_toc: bool = True,
) -> list[MeetingReference]:
    references: list[MeetingReference] = []
    seen: set[str] = set()
    for match in ROW_RE.finditer(html):
        session = _compact_session(match.group("session"))
        label = unescape(match.group("label")).strip()
        href = match.group("href")
        params = parse_qs(urlparse(href).query)
        fino = _first(params.get("FINO"))
        if not fino or fino in seen:
            continue
        kgno = _first(params.get("KGNO"))
        unid = _first(params.get("UNID"))
        date_label = DATE_LABEL_RE.match(label)
        if date_label is None:
            continue
        rest = date_label.group("rest").strip()
        if skip_toc and "目次" in rest:
            continue
        meeting_date = date(
            year,
            int(date_label.group("month")),
            int(date_label.group("day")),
        )
        if since is not None and meeting_date < since:
            continue
        if until is not None and meeting_date > until:
            continue
        issue = _parse_issue(rest)
        meeting_session, meeting_name = _session_and_name(session)
        title_hint = f"{session} {label}".strip()
        view_url = urljoin(minutes_base_url.rstrip("/") + "/", href)
        fetch_url = _act203_url(minutes_base_url, fino)
        seen.add(fino)
        references.append(
            MeetingReference(
                municipality_code=municipality_code,
                source_system=SOURCE_SYSTEM,
                source_meeting_id=fino,
                url=view_url,
                discovered_date=meeting_date,
                title_hint=title_hint,
                session=meeting_session,
                name=meeting_name,
                issue=issue,
                fetch_url=fetch_url,
                extra={"kgno": kgno, "unid": unid, "label": label, "year": year},
            )
        )
    references.sort(key=lambda item: (item.discovered_date or date.min, item.issue or 0, item.source_meeting_id))
    return references


def parse_meeting_html(
    html: str,
    reference: MeetingReference,
) -> ParsedMeeting:
    if reference.discovered_date is None:
        raise ValueError("MeetingReference.discovered_date is required to parse")
    html = STYLE_RE.sub("", SCRIPT_RE.sub("", html))
    parts = HUID_SPLIT_RE.split(html)
    speeches: list[ParsedSpeech] = []
    order = 1
    # parts[0] is preamble (style/script). Speeches start at index 1.
    for index in range(1, len(parts), 2):
        huid = parts[index]
        source_speech_id = huid.removeprefix("HUID") if huid.upper().startswith("HUID") else huid
        body_html = parts[index + 1] if index + 1 < len(parts) else ""
        text = _html_fragment_to_text(body_html)
        if not text:
            continue
        if text.startswith("function "):
            continue
        speaker, speech_text = _parse_speaker_and_text(text)
        source_url = _speech_source_url(reference.fetch_url or reference.url, huid)
        speeches.append(
            ParsedSpeech(
                source_speech_id=source_speech_id,
                order=order,
                speaker=speaker,
                text=speech_text,
                start_page=None,
                source_url=source_url,
            )
        )
        order += 1
    if not speeches:
        raise ValueError(f"no speeches found for FINO={reference.source_meeting_id}")
    return ParsedMeeting(
        source_meeting_id=reference.source_meeting_id,
        session=_compact_session(reference.session) if reference.session else None,
        name=reference.name or PLENARY_NAME,
        date=reference.discovered_date,
        issue=reference.issue,
        speeches=tuple(speeches),
        source_url=reference.url,
        pdf_url=None,
    )


def parse_listing_bytes(data: bytes, **kwargs) -> list[MeetingReference]:
    return parse_listing_html(decode_html_bytes(data), **kwargs)


def parse_meeting_bytes(data: bytes, reference: MeetingReference) -> ParsedMeeting:
    return parse_meeting_html(decode_html_bytes(data), reference)


def parse_committee_sflgs(html: str, year: int) -> list[str]:
    """g08v_views.asp の年リンクから、個別委員会の Sflg を返す。"""
    found: list[str] = []
    seen: set[str] = set()
    for match in COMMITTEE_YEAR_SFLG_RE.finditer(html):
        sflg = match.group(1)
        link_year = int(match.group(2))
        if link_year != year or sflg in AGGREGATE_SFLG or sflg in seen:
            continue
        seen.add(sflg)
        found.append(sflg)
    return found


def parse_iframe_listing_url(html: str, minutes_base_url: str) -> str | None:
    match = IFRAME_SRC_RE.search(html)
    if match is None:
        return None
    src = unescape(match.group(1)).strip()
    if not src:
        return None
    joined = urljoin(minutes_base_url.rstrip("/") + "/", src)
    params = parse_qs(urlparse(joined).query)
    act = _first(params.get("ACT"))
    if act != "100":
        return None
    return joined


def listing_is_empty(html: str) -> bool:
    return any(marker in html for marker in EMPTY_LISTING_MARKERS)


def _act203_url(minutes_base_url: str, fino: str) -> str:
    return (
        f"{minutes_base_url.rstrip('/')}/cgi/voiweb.exe"
        f"?ACT=203&FINO={fino}&HATSUGENMODE=1&HYOUJIMODE=0&STYLE=0"
    )


def _speech_source_url(fetch_url: str, huid: str) -> str:
    base = fetch_url.split("#", 1)[0]
    return f"{base}#{huid}"


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0]


def _parse_issue(rest: str) -> int | None:
    match = ISSUE_RE.match(rest)
    if match is None:
        return None
    return int(match.group("issue"))


def _compact_session(value: str) -> str:
    return re.sub(r"[　\s]+", "", unescape(value)).strip()


def _session_and_name(session: str) -> tuple[str, str]:
    compact = _compact_session(session)
    match = COMMITTEE_NAME_RE.match(compact)
    if match is None:
        return compact, PLENARY_NAME
    head = match.group("session").strip()
    name = match.group("name").strip()
    return (head or compact, name)


def _html_fragment_to_text(fragment: str) -> str:
    fragment = STYLE_RE.sub("", SCRIPT_RE.sub("", fragment))
    text = re.sub(r"(?i)<br\s*/?>", "\n", fragment)
    text = re.sub(r"(?i)</?p[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    script_cut = re.search(r"\nfunction\s+\w+\s*\(", text)
    if script_cut:
        text = text[: script_cut.start()]
    lines = [line.rstrip() for line in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


def _parse_speaker_and_text(text: str) -> tuple[ParsedSpeaker, str]:
    first, _, rest = text.partition("\n")
    first = first.strip()
    if not first:
        return ParsedSpeaker(name="（不明）"), text

    if first.startswith("令和") and ("会" in first or "会議録" in text[:80]):
        return ParsedSpeaker(name=HEADER_NAME, role="議事"), text

    if first.startswith("（参照") or first.startswith("（写）"):
        return ParsedSpeaker(name=first, role="議事"), text

    mark = first[0]
    remainder = first[1:] if mark in {"○", "◎", "◆", "△"} else first

    if mark in {"○", "◎", "◆"}:
        member = MEMBER_RE.match(remainder)
        if member:
            body = _join_speech(member.group("text"), rest)
            return (
                ParsedSpeaker(name=member.group("name").strip(), position="議員"),
                body,
            )
        chair = CHAIR_OR_EXEC_RE.match(remainder)
        if chair:
            body = _join_speech(chair.group("inline") or "", rest)
            return (
                ParsedSpeaker(
                    name=chair.group("name").strip(),
                    position=chair.group("position").strip(),
                ),
                body,
            )
        fallback = NAME_THEN_TEXT_RE.match(remainder)
        if fallback:
            body = _join_speech(fallback.group("text"), rest)
            return ParsedSpeaker(name=fallback.group("name").strip()), body

    if mark == "△":
        heading = remainder.strip() or first
        body = _join_speech(heading, rest)
        return ParsedSpeaker(name=heading, role="議事"), body or heading

    return ParsedSpeaker(name=first), text


def _join_speech(head: str, rest: str) -> str:
    head = head.strip()
    rest = rest.strip()
    if head and rest:
        return f"{head}\n{rest}"
    return head or rest
