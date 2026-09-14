from __future__ import annotations

import re
from datetime import date
from html import unescape
from urllib.parse import parse_qs, urljoin, urlparse

from local_council_system.http_client import decode_html_bytes
from local_council_system.models import MeetingReference, ParsedMeeting, ParsedSpeaker, ParsedSpeech

SOURCE_SYSTEM = "dbsr"
PLENARY_NAME = "本会議"
SKIP_MARKERS = ("名簿", "資料")

ITEM_RE = re.compile(
    r'<li class="result-document__item">(.*?)</li>',
    re.DOTALL | re.IGNORECASE,
)
LINK_RE = re.compile(
    r'<a href="(?P<href>[^"]+)">(?P<title>[^<]+)</a>',
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"開催日:</span>\s*(?P<date>\d{4}-\d{2}-\d{2})",
)
ISSUE_RE = re.compile(r"（第(?P<issue>[0-9０-９]+)日）\s*$")
VOICE_BLOCK_RE = re.compile(
    r'<li\s+class="voice-block[^"]*"(?P<attrs>[^>]*)>(?P<body>.*?)</li>',
    re.DOTALL | re.IGNORECASE,
)
VOICE_CODE_RE = re.compile(r'data-voice_code="(?P<code>\d+)"', re.IGNORECASE)
VOICE_TITLE_RE = re.compile(r'data-voice-title="(?P<title>[^"]*)"', re.IGNORECASE)
VOICE_TEXT_RE = re.compile(
    r'<p\s+class="voice__text"[^>]*>(?P<html>.*?)</p>',
    re.DOTALL | re.IGNORECASE,
)
SPEECH_SPLIT_RE = re.compile(r"(?m)^(?P<order>\d+)\s*[:：]\s*")
MEMBER_RE = re.compile(
    r"^[◯○◎](?P<num>\d+)番（(?P<name>.+?)君）(?P<text>.*)$",
    re.DOTALL,
)
ROLE_RE = re.compile(
    r"^[◯○◎](?P<position>.+?)（(?P<name>.+?)君）(?P<text>.*)$",
    re.DOTALL,
)
MEMBER_TITLE_RE = re.compile(r"^[◯○◎](?P<num>\d+)番（(?P<name>.+?)君）$")
ROLE_TITLE_RE = re.compile(r"^[◯○◎](?P<position>.+?)（(?P<name>.+?)君）$")
ZEN_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
SCRIPT_RE = re.compile(r"(?is)<script[^>]*>.*?</script>")
STYLE_RE = re.compile(r"(?is)<style[^>]*>.*?</style>")


def parse_listing_html(
    html: str,
    *,
    municipality_code: str,
    base_url: str,
    since: date | None = None,
    until: date | None = None,
) -> list[MeetingReference]:
    references: list[MeetingReference] = []
    seen: set[str] = set()
    for item in ITEM_RE.findall(html):
        link = LINK_RE.search(item)
        if link is None:
            continue
        title = unescape(link.group("title")).replace("\u3000", " ").strip()
        if not _is_body_document(title):
            continue
        href = unescape(link.group("href")).split("#", 1)[0]
        params = parse_qs(urlparse(href).query)
        source_id = _first(params.get("Id"))
        if not source_id or source_id in seen:
            continue
        date_match = DATE_RE.search(item)
        if date_match is None:
            continue
        meeting_date = date.fromisoformat(date_match.group("date"))
        if since is not None and meeting_date < since:
            continue
        if until is not None and meeting_date > until:
            continue
        session, name, issue = _session_name_issue(title)
        view_url = urljoin(base_url.rstrip("/") + "/", href)
        seen.add(source_id)
        references.append(
            MeetingReference(
                municipality_code=municipality_code,
                source_system=SOURCE_SYSTEM,
                source_meeting_id=source_id,
                url=view_url,
                discovered_date=meeting_date,
                title_hint=title,
                session=session,
                name=name,
                issue=issue,
                fetch_url=view_url,
                extra={"kind": "本文"},
            )
        )
    references.sort(
        key=lambda item: (item.discovered_date or date.min, item.issue or 0, item.source_meeting_id)
    )
    return references


def parse_meeting_html(html: str, reference: MeetingReference) -> ParsedMeeting:
    if reference.discovered_date is None:
        raise ValueError("MeetingReference.discovered_date is required to parse")
    source_url = reference.fetch_url or reference.url
    speeches = _parse_voice_blocks(html, source_url)
    if not speeches:
        speeches = _parse_speeches(_html_to_text(html), source_url)
    if not speeches:
        raise ValueError(f"no speeches found for Id={reference.source_meeting_id}")
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


def parse_listing_bytes(data: bytes, **kwargs) -> list[MeetingReference]:
    return parse_listing_html(decode_html_bytes(data), **kwargs)


def parse_meeting_bytes(data: bytes, reference: MeetingReference) -> ParsedMeeting:
    return parse_meeting_html(decode_html_bytes(data), reference)


def _is_body_document(title: str) -> bool:
    if any(marker in title for marker in SKIP_MARKERS):
        return False
    return title.endswith("本文")


def _session_name_issue(title: str) -> tuple[str | None, str, int | None]:
    core = re.sub(r"\s*本文$", "", title).strip()
    issue = None
    issue_match = ISSUE_RE.search(core)
    if issue_match:
        issue = int(issue_match.group("issue").translate(ZEN_DIGITS))
        core = core[: issue_match.start()].strip()
    if "定例市会" in core or "臨時市会" in core:
        return core, PLENARY_NAME, issue
    return core, core, issue


def _parse_voice_blocks(html: str, source_url: str) -> list[ParsedSpeech]:
    speeches: list[ParsedSpeech] = []
    for match in VOICE_BLOCK_RE.finditer(html):
        attrs = match.group("attrs")
        code_match = VOICE_CODE_RE.search(attrs)
        title_match = VOICE_TITLE_RE.search(attrs)
        text_match = VOICE_TEXT_RE.search(match.group("body"))
        if code_match is None or text_match is None:
            continue
        order = int(code_match.group("code"))
        title = unescape(title_match.group("title")).strip() if title_match else ""
        body = _html_to_text(text_match.group("html"))
        speaker = _speaker_from_title(title)
        text = _strip_title(body, title)
        if not text:
            continue
        speeches.append(
            ParsedSpeech(
                source_speech_id=str(order),
                order=order,
                speaker=speaker,
                text=text,
                start_page=None,
                source_url=f"{source_url.split('#', 1)[0]}#voice-{order}",
            )
        )
    return speeches


def _speaker_from_title(title: str) -> ParsedSpeaker:
    member = MEMBER_TITLE_RE.match(title)
    if member:
        return ParsedSpeaker(name=_person_name(member.group("name")), position="議員")
    role = ROLE_TITLE_RE.match(title)
    if role:
        return ParsedSpeaker(
            name=_person_name(role.group("name")),
            position=role.group("position").strip(),
        )
    return ParsedSpeaker(name=_person_name(title) or "（不明）")


def _strip_title(text: str, title: str) -> str:
    if not title:
        return text.strip()
    if title in text:
        before, _, after = text.partition(title)
        return _join(before.strip(), after.lstrip("\u3000 \n"))
    return text.strip()


def _html_to_text(html: str) -> str:
    html = STYLE_RE.sub("", SCRIPT_RE.sub("", html))
    text = re.sub(r"(?i)<br\s*/?>", "\n", html)
    text = re.sub(r"(?i)</p\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text).replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def _parse_speeches(text: str, source_url: str) -> list[ParsedSpeech]:
    parts = SPEECH_SPLIT_RE.split(text)
    speeches: list[ParsedSpeech] = []
    for index in range(1, len(parts), 2):
        order = int(parts[index])
        body = parts[index + 1] if index + 1 < len(parts) else ""
        speaker, speech_text = _parse_speaker_and_text(body)
        if not speech_text:
            continue
        speeches.append(
            ParsedSpeech(
                source_speech_id=None,
                order=order,
                speaker=speaker,
                text=speech_text,
                start_page=None,
                source_url=f"{source_url.split('#', 1)[0]}#speech-{order}",
            )
        )
    return speeches


def _parse_speaker_and_text(text: str) -> tuple[ParsedSpeaker, str]:
    first, _, rest = text.partition("\n")
    first = first.strip()
    member = MEMBER_RE.match(first)
    if member:
        return (
            ParsedSpeaker(name=_person_name(member.group("name")), position="議員"),
            _join(member.group("text"), rest),
        )
    role = ROLE_RE.match(first)
    if role:
        return (
            ParsedSpeaker(
                name=_person_name(role.group("name")),
                position=role.group("position").strip(),
            ),
            _join(role.group("text"), rest),
        )
    return ParsedSpeaker(name=_person_name(first) or "（不明）"), rest.strip() or first


def _person_name(value: str) -> str:
    return re.sub(r"[ \u3000]+", " ", (value or "").replace("\u3000", " ")).strip()


def _join(head: str, rest: str) -> str:
    head = (head or "").strip()
    rest = rest.strip()
    if head and rest:
        return f"{head}\n{rest}"
    return head or rest


def _first(values: list[str] | None) -> str | None:
    if not values:
        return None
    return values[0]
