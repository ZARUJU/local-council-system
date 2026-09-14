from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class DiscoveryContext:
    municipality_code: str
    since: datetime | None
    until: datetime | None = None


@dataclass(frozen=True)
class MeetingReference:
    municipality_code: str
    source_system: str
    source_meeting_id: str
    url: str
    discovered_date: date | None = None
    title_hint: str | None = None
    session: str | None = None
    name: str | None = None
    issue: int | None = None
    fetch_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedSpeaker:
    name: str
    yomi: str | None = None
    group: str | None = None
    position: str | None = None
    role: str | None = None


@dataclass(frozen=True)
class ParsedSpeech:
    source_speech_id: str | None
    order: int
    speaker: ParsedSpeaker
    text: str
    start_page: int | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class ParsedMeeting:
    source_meeting_id: str
    session: str | None
    name: str
    date: date
    issue: int | None
    speeches: tuple[ParsedSpeech, ...]
    source_url: str
    pdf_url: str | None = None


@dataclass(frozen=True)
class CanonicalSpeaker:
    name: str
    yomi: str | None
    group: str | None
    position: str | None
    role: str | None


@dataclass(frozen=True)
class CanonicalSpeech:
    id: str
    order: int
    source_identity: dict[str, str | None]
    speaker: CanonicalSpeaker
    text: str
    start_page: int | None
    source_url: str | None


@dataclass(frozen=True)
class CanonicalMeeting:
    schema_version: str
    id: str
    municipality_code: str
    source_identity: dict[str, str]
    session: str | None
    name: str
    date: str
    issue: int | None
    speeches: tuple[CanonicalSpeech, ...]
    source_url: str
    pdf_url: str | None
