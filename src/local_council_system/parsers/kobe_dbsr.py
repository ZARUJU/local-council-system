from __future__ import annotations

import re
from datetime import date
from html import unescape
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlparse, urlunparse

from local_council_system.http_client import decode_html_bytes
from local_council_system.models import MeetingReference, ParsedMeeting, ParsedSpeaker, ParsedSpeech

SOURCE_SYSTEM = "dbsr"
PLENARY_NAME = "本会議"
SKIP_MARKERS = ("名簿", "資料", "委員会")

ITEM_RE = re.compile(
    r'<li class="result-document__item">(.*?)</li>',
    re.DOTALL | re.IGNORECASE,
)
CLASSIC_ITEM_RE = re.compile(
    r'<div class="result-document">(.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
CURRENT_PAGE_RE = re.compile(r'aria-current="page">\s*(?P<page>\d+)', re.IGNORECASE)
PAGE_HREF_RE = re.compile(
    r'href="(?P<href>[^"]*Template=list[^"]*Page=(?P<page>\d+)[^"]*)"',
    re.IGNORECASE,
)
PAGE_NAME_VALUE_RE = re.compile(
    r'name="Page"\s+value="(?P<page>\d+)"',
    re.IGNORECASE,
)
PAGE_VALUE_NAME_RE = re.compile(
    r'value="(?P<page>\d+)"\s+name="Page"',
    re.IGNORECASE,
)
LINK_RE = re.compile(
    r'<a href="(?P<href>[^"]+)">(?P<title>[^<]+)</a>',
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"開催日:</span>\s*(?P<date>\d{4}-\d{2}-\d{2})",
)
CLASSIC_ISO_DATE_RE = re.compile(
    r'class="result-document-date">\s*(?P<date>\d{4}-\d{2}-\d{2})',
    re.IGNORECASE,
)
CLASSIC_JP_DATE_RE = re.compile(
    r"開催日[:：]\s*(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日",
)
ISSUE_RE = re.compile(r"（第(?P<issue>[0-9０-９]+)日目?）\s*$")
VOICE_BLOCK_RE = re.compile(
    r'<li\s+class="voice-block[^"]*"(?P<attrs>[^>]*)>(?P<body>.*?)</li>',
    re.DOTALL | re.IGNORECASE,
)
PAGE_VOICE_RE = re.compile(
    r'<li\s+class="page-text__voice[^"]*"(?P<attrs>[^>]*)>(?P<body>.*?)</li>',
    re.DOTALL | re.IGNORECASE,
)
VOICE_NO_RE = re.compile(r'data-voice-no="(?P<no>\d+)"', re.IGNORECASE)
VOICE_CODE_RE = re.compile(r'data-voice_code="(?P<code>\d+)"', re.IGNORECASE)
VOICE_TITLE_RE = re.compile(r'data-voice-title="(?P<title>[^"]*)"', re.IGNORECASE)
VOICE_TEXT_RE = re.compile(
    r'<p\s+class="voice__text"[^>]*>(?P<html>.*?)</p>',
    re.DOTALL | re.IGNORECASE,
)
PAGE_TEXT_RE = re.compile(
    r'<p\s+class="page-text__text[^"]*"[^>]*>(?P<html>.*?)</p>',
    re.DOTALL | re.IGNORECASE,
)
VOICE_ID_VALUE_RE = re.compile(r'name="VoiceID\[\]"[^>]*value="(?P<vid>\d+)"', re.IGNORECASE)
VOICE_ID_VALUE_RE2 = re.compile(r'value="(?P<vid>\d+)"[^>]*name="VoiceID\[\]"', re.IGNORECASE)
SPEECH_SPLIT_RE = re.compile(r"(?m)^(?P<order>\d+)\s*[:：]\s*")
MEMBER_RE = re.compile(
    r"^[◯○◎](?P<num>[0-9０-９]+)番(?:議員)?（(?P<name>.+?)(?:君)?）(?P<text>.*)$",
    re.DOTALL,
)
ROLE_RE = re.compile(
    r"^[◯○◎](?P<position>.+?)（(?P<name>.+?)(?:君)?）(?P<text>.*)$",
    re.DOTALL,
)
NAKED_RE = re.compile(
    r"^[◯○◎](?P<name>.+?)君(?P<text>.*)$",
    re.DOTALL,
)
MEMBER_TITLE_RE = re.compile(r"^[◯○◎]?(?P<num>[0-9０-９]+)番(?:議員)?（(?P<name>.+?)(?:君)?）$")
ROLE_TITLE_RE = re.compile(r"^[◯○◎]?(?P<position>.+?)（(?P<name>.+?)(?:君)?）$")
NAKED_TITLE_RE = re.compile(r"^[◯○◎]?(?P<name>.+?)君$")
DOCPAGE_VOICE_RE = re.compile(
    r'<div\s+class="docpage-voice-text-box[^"]*"[^>]*(?:id="VoiceNo(?P<id>\d+)")?[^>]*>(?P<body>.*?)</div>',
    re.DOTALL | re.IGNORECASE,
)
DOCPAGE_TEXT_RE = re.compile(
    r'<p\s+class="docpage-voice-text"[^>]*>(?P<html>.*?)</p>',
    re.DOTALL | re.IGNORECASE,
)
DOCPAGE_NO_RE = re.compile(r'data-voiceno="(?P<no>\d+)"', re.IGNORECASE)
LEADING_VOICE_NO_RE = re.compile(r"^\d+\s*")
COMMAND_TITLE_RE = re.compile(
    r'class="command__title">(?P<title>[^<]+)',
    re.IGNORECASE,
)
SPEAKER_ITEM_RE = re.compile(
    r'<li\s+class="speaker__item[^"]*"[^>]*data-voice-no="(?P<no>\d+)"[^>]*>(?P<body>.*?)</li>',
    re.DOTALL | re.IGNORECASE,
)
VOICE_NAME_RE = re.compile(
    r'class="voice__name[^"]*">(?P<name>[^<]+)',
    re.IGNORECASE,
)
LEADING_ORDER_RE = re.compile(r"^\d+[:：]\s*")
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
    chunks = ITEM_RE.findall(html)
    chunks.extend(CLASSIC_ITEM_RE.findall(html))
    for item in chunks:
        link = LINK_RE.search(item)
        if link is None:
            continue
        title = unescape(link.group("title")).replace("\u3000", " ").strip()
        if not _is_body_document(title):
            continue
        href = unescape(link.group("href")).split("#", 1)[0]
        params = parse_qs(urlparse(href).query)
        source_id = _first(params.get("Id")) or _first(params.get("DocumentID"))
        if not source_id or source_id in seen:
            continue
        meeting_date = _listing_date(item)
        if meeting_date is None:
            continue
        if since is not None and meeting_date < since:
            continue
        if until is not None and meeting_date > until:
            continue
        session, name, issue = _session_name_issue(title)
        view_url = rewrite_document_fetch_url(urljoin(base_url.rstrip("/") + "/", href))
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


def listing_page_numbers(html: str) -> set[int]:
    """検索結果一覧に出ているページ番号。現在ページと Page ボタンを含む。"""
    pages = {int(match.group("page")) for match in PAGE_NAME_VALUE_RE.finditer(html)}
    pages.update(int(match.group("page")) for match in PAGE_VALUE_NAME_RE.finditer(html))
    current = CURRENT_PAGE_RE.search(html)
    if current:
        pages.add(int(current.group("page")))
    if not pages:
        pages.add(1)
    return pages


def listing_page_hrefs(html: str, base_url: str) -> set[str]:
    """一覧 HTML に出ている Page= 付きの一覧 URL。ビューアパスが ephemeral な dbsr 向け。"""
    return set(listing_page_hrefs_by_page(html, base_url).values())


def listing_page_hrefs_by_page(html: str, base_url: str) -> dict[int, str]:
    """ページ番号 → 一覧 URL。同じ番号が複数あるときは先に出た href を使う。"""
    urls: dict[int, str] = {}
    for match in PAGE_HREF_RE.finditer(html):
        page = int(match.group("page"))
        if page in urls:
            continue
        href = unescape(match.group("href")).split("#", 1)[0]
        urls[page] = urljoin(base_url.rstrip("/") + "/", href)
    return urls


def parse_meeting_html(html: str, reference: MeetingReference) -> ParsedMeeting:
    if reference.discovered_date is None:
        raise ValueError("MeetingReference.discovered_date is required to parse")
    source_url = reference.fetch_url or reference.url
    speeches = _parse_voice_blocks(html, source_url)
    if not speeches:
        speeches = _parse_page_voices(html, source_url)
    if not speeches:
        speeches = _parse_docpage_voices(html, source_url)
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


def rewrite_document_fetch_url(url: str) -> str:
    """廿日市市など frameset 本文を、全発言の doc-page に付け替える。"""
    parsed = urlparse(url)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    template = params.get("Template", "")
    if template not in {"doc-one-frame", "doc-page"}:
        return url
    params["Template"] = "doc-page"
    params["VoiceType"] = "all"
    return urlunparse(parsed._replace(query=urlencode(params)))


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
    if "定例会" in core or "臨時会" in core:
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


def _parse_page_voices(html: str, source_url: str) -> list[ParsedSpeech]:
    speeches: list[ParsedSpeech] = []
    titles = _speaker_titles_by_voice_no(html)
    for match in PAGE_VOICE_RE.finditer(html):
        attrs = match.group("attrs")
        no_match = VOICE_NO_RE.search(attrs)
        if no_match is None:
            continue
        order = int(no_match.group("no"))
        body = match.group("body")
        vid_match = VOICE_ID_VALUE_RE.search(body) or VOICE_ID_VALUE_RE2.search(body)
        text_match = PAGE_TEXT_RE.search(body)
        if text_match is None:
            continue
        title_match = COMMAND_TITLE_RE.search(body)
        title = unescape(title_match.group("title")).strip() if title_match else ""
        if not title or title.endswith("本文"):
            title = titles.get(order, "")
        body_text = LEADING_ORDER_RE.sub("", _html_to_text(text_match.group("html")), count=1).strip()
        if title:
            speaker = _speaker_from_title(title)
            text = _strip_title(body_text, title)
        else:
            speaker, text = _parse_speaker_and_text(body_text)
        if not text:
            continue
        source_id = vid_match.group("vid") if vid_match else str(order)
        speeches.append(
            ParsedSpeech(
                source_speech_id=source_id,
                order=order,
                speaker=speaker,
                text=text,
                start_page=None,
                source_url=f"{source_url.split('#', 1)[0]}#voice-{source_id}",
            )
        )
    return speeches


def _parse_docpage_voices(html: str, source_url: str) -> list[ParsedSpeech]:
    speeches: list[ParsedSpeech] = []
    for match in DOCPAGE_VOICE_RE.finditer(html):
        body = match.group("body")
        no_match = DOCPAGE_NO_RE.search(body)
        order_raw = match.group("id")
        if no_match:
            order = int(no_match.group("no"))
        elif order_raw:
            order = int(order_raw)
        else:
            continue
        text_match = DOCPAGE_TEXT_RE.search(body)
        if text_match is None:
            continue
        body_text = LEADING_VOICE_NO_RE.sub("", _html_to_text(text_match.group("html")), count=1).strip()
        speaker, text = _parse_speaker_and_text(body_text)
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


def _speaker_titles_by_voice_no(html: str) -> dict[int, str]:
    titles: dict[int, str] = {}
    for match in SPEAKER_ITEM_RE.finditer(html):
        name_match = VOICE_NAME_RE.search(match.group("body"))
        if name_match is None:
            continue
        titles[int(match.group("no"))] = unescape(name_match.group("name")).strip()
    return titles


def _listing_date(item: str) -> date | None:
    iso = DATE_RE.search(item) or CLASSIC_ISO_DATE_RE.search(item)
    if iso:
        return date.fromisoformat(iso.group("date"))
    jp = CLASSIC_JP_DATE_RE.search(item)
    if jp:
        return date(int(jp.group("year")), int(jp.group("month")), int(jp.group("day")))
    return None


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
    naked = NAKED_TITLE_RE.match(title)
    if naked:
        return ParsedSpeaker(name=_person_name(naked.group("name")))
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
    lines = [line for line in text.split("\n")]
    while lines and LEADING_ORDER_RE.fullmatch(lines[0].strip()):
        lines.pop(0)
    for index, line in enumerate(lines):
        first = line.strip()
        member = MEMBER_RE.match(first)
        role = ROLE_RE.match(first)
        naked = NAKED_RE.match(first)
        match = member or role or naked
        if match is None:
            continue
        rest = "\n".join(lines[index + 1 :])
        if member:
            return (
                ParsedSpeaker(name=_person_name(member.group("name")), position="議員"),
                _join(member.group("text"), rest),
            )
        if role:
            return (
                ParsedSpeaker(
                    name=_person_name(role.group("name")),
                    position=role.group("position").strip(),
                ),
                _join(role.group("text"), rest),
            )
        return (
            ParsedSpeaker(name=_person_name(naked.group("name"))),
            _join(naked.group("text"), rest),
        )
    text = "\n".join(lines)
    first, _, rest = text.partition("\n")
    first = first.strip()
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
