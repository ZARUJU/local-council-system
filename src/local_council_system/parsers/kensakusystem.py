from __future__ import annotations

import re
from datetime import date
from html import unescape

from local_council_system.models import MeetingReference, ParsedMeeting, ParsedSpeech
from local_council_system.parsers.kobe_dbsr import _html_to_text, _parse_speaker_and_text

SOURCE_SYSTEM = "kensakusystem"
PLENARY_NAME = "本会議"
SKIP_SESSION_MARKERS = ("委員会",)
PLENARY_MARKERS = ("定例会", "臨時会")
CODE_RE = re.compile(r"See\.exe\?Code=(?P<code>[A-Za-z0-9]+)", re.IGNORECASE)
TREEDEPTH_RE = re.compile(r"treedepth\.value='(?P<label>[^']+)'")
DAY_RE = re.compile(
    r'href="ResultFrame\.exe\?[^"]*?fileName=(?P<file>[^&"\']+)[^"]*"'
    r"[^>]*>((?:(?!</[Aa]>).)*?)（(?:第\s*(?P<issue>\d+)\s*日\s*)?\s*(?P<month>\d{1,2})月\s*(?P<day>\d{1,2})日）",
    re.IGNORECASE | re.DOTALL,
)
SPEAKER_START_RE = re.compile(r"(?m)^[◯○◎]")
ZEN_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
SPACE_RE = re.compile(r"[ \u3000]+")


def extract_session_code(html: str) -> str | None:
    match = CODE_RE.search(html)
    if match is None:
        return None
    return match.group("code")


def era_year_label(year: int) -> str:
    if year >= 2019:
        number = year - 2018
        if number == 1:
            return "令和元年"
        return f"令和 {number}年" if number < 10 else f"令和{number}年"
    number = year - 1988
    if number == 1:
        return "平成元年"
    return f"平成 {number}年" if number < 10 else f"平成{number}年"


def parse_session_labels(html: str, year_label: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in TREEDEPTH_RE.finditer(html):
        label = unescape(match.group("label"))
        if label in seen:
            continue
        if not label.startswith(year_label):
            continue
        if not _is_plenary_session(label):
            continue
        seen.add(label)
        found.append(label)
    return found


def parse_day_links(
    html: str,
    *,
    municipality_code: str,
    base_url: str,
    session_label: str,
    year: int,
    since: date | None = None,
    until: date | None = None,
) -> list[MeetingReference]:
    session = _session_name(session_label)
    references: list[MeetingReference] = []
    seen: set[str] = set()
    sequential = 0
    for match in DAY_RE.finditer(html):
        file_name = unescape(match.group("file")).strip()
        if not file_name or file_name in seen:
            continue
        seen.add(file_name)
        sequential += 1
        issue_raw = match.group("issue")
        issue = int(issue_raw) if issue_raw else sequential
        meeting_date = date(
            year,
            int(match.group("month")),
            int(match.group("day")),
        )
        if since is not None and meeting_date < since:
            continue
        if until is not None and meeting_date > until:
            continue
        url = f"{base_url.rstrip('/')}/cgi-bin3/ResultFrame.exe?fileName={file_name}"
        references.append(
            MeetingReference(
                municipality_code=municipality_code,
                source_system=SOURCE_SYSTEM,
                source_meeting_id=file_name,
                url=url,
                discovered_date=meeting_date,
                title_hint=f"{session}（{meeting_date.month}月{meeting_date.day}日）",
                session=session,
                name=PLENARY_NAME,
                issue=issue,
                fetch_url=url,
                extra={"file_name": file_name},
            )
        )
    return references


def parse_meeting_html(html: str, reference: MeetingReference) -> ParsedMeeting:
    if reference.discovered_date is None:
        raise ValueError("MeetingReference.discovered_date is required to parse")
    source_url = reference.fetch_url or reference.url
    speeches = _parse_print_all(_html_to_text(html), source_url)
    if not speeches:
        raise ValueError(f"no speeches found for fileName={reference.source_meeting_id}")
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


def _parse_print_all(text: str, source_url: str) -> list[ParsedSpeech]:
    starts = list(SPEAKER_START_RE.finditer(text))
    speeches: list[ParsedSpeech] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[match.start() : end].strip()
        speaker, speech_text = _parse_speaker_and_text(block)
        if not speech_text:
            continue
        order = len(speeches) + 1
        speeches.append(
            ParsedSpeech(
                source_speech_id=str(order),
                order=order,
                speaker=speaker,
                text=speech_text,
                start_page=None,
                source_url=f"{source_url.split('#', 1)[0]}#speech-{order}",
            )
        )
    return speeches


def _is_plenary_session(label: str) -> bool:
    if any(marker in label for marker in SKIP_SESSION_MARKERS):
        return False
    return any(marker in label for marker in PLENARY_MARKERS)


def _session_name(label: str) -> str:
    return SPACE_RE.sub(" ", label.translate(ZEN_DIGITS)).strip()
