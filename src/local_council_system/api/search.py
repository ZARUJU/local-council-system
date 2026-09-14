from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path


SPEECH_FILTERS = frozenset(
    {
        "any",
        "speaker",
        "speechNumber",
        "speakerPosition",
        "speakerGroup",
        "speakerRole",
        "speechID",
    }
)
SEARCH_FILTERS = SPEECH_FILTERS | {
    "prefecture",
    "municipality",
    "municipalityCode",
    "nameOfMeeting",
    "session",
    "from",
    "until",
    "meetingID",
}

MEETING_LIST_JOIN = """
FROM meetings
JOIN municipalities ON municipalities.code = meetings.municipality_code
"""
SPEECH_JOIN = """
FROM speeches
JOIN meetings ON meetings.id = speeches.meeting_id
JOIN municipalities ON municipalities.code = meetings.municipality_code
"""


@dataclass(frozen=True)
class SearchParams:
    start_record: int = 1
    maximum_records: int = 30
    prefecture: str | None = None
    municipality: str | None = None
    municipality_code: str | None = None
    name_of_meeting: str | None = None
    session: str | None = None
    any_text: str | None = None
    speaker: str | None = None
    date_from: date | None = None
    date_until: date | None = None
    speech_number: int | None = None
    speaker_position: str | None = None
    speaker_group: str | None = None
    speaker_role: str | None = None
    speech_id: str | None = None
    meeting_id: str | None = None

    def active_filters(self) -> list[str]:
        mapping = {
            "prefecture": self.prefecture,
            "municipality": self.municipality,
            "municipalityCode": self.municipality_code,
            "nameOfMeeting": self.name_of_meeting,
            "session": self.session,
            "any": self.any_text,
            "speaker": self.speaker,
            "from": self.date_from,
            "until": self.date_until,
            "speechNumber": self.speech_number,
            "speakerPosition": self.speaker_position,
            "speakerGroup": self.speaker_group,
            "speakerRole": self.speaker_role,
            "speechID": self.speech_id,
            "meetingID": self.meeting_id,
        }
        return [key for key, value in mapping.items() if value not in (None, "")]

    def has_search_condition(self) -> bool:
        return bool(self.active_filters())

    def has_speech_condition(self) -> bool:
        return any(key in SPEECH_FILTERS for key in self.active_filters())


def open_readonly(database: Path) -> sqlite3.Connection:
    uri = f"file:{database.resolve().as_posix()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def search_speeches(
    connection: sqlite3.Connection,
    params: SearchParams,
) -> tuple[int, list[sqlite3.Row]]:
    where, values = _speech_where(params)
    total = connection.execute(
        f"SELECT COUNT(*) {SPEECH_JOIN} {where}",
        values,
    ).fetchone()[0]
    rows = connection.execute(
        f"""
        SELECT
            speeches.id AS speech_id,
            meetings.id AS meeting_id,
            municipalities.prefecture AS prefecture,
            municipalities.name AS municipality,
            meetings.municipality_code AS municipality_code,
            meetings.session AS session,
            meetings.name AS name_of_meeting,
            meetings.date AS date,
            speeches.speech_order AS speech_order,
            speeches.speaker_name AS speaker,
            speeches.speaker_yomi AS speaker_yomi,
            speeches.speaker_group AS speaker_group,
            speeches.speaker_position AS speaker_position,
            speeches.speaker_role AS speaker_role,
            speeches.speech_text AS speech,
            speeches.start_page AS start_page,
            speeches.source_url AS speech_url,
            meetings.source_url AS meeting_url,
            meetings.pdf_url AS pdf_url
        {SPEECH_JOIN}
        {where}
        ORDER BY meetings.date DESC, meetings.id ASC, speeches.speech_order ASC
        LIMIT ? OFFSET ?
        """,
        [*values, params.maximum_records, params.start_record - 1],
    ).fetchall()
    return total, rows


def search_meetings(
    connection: sqlite3.Connection,
    params: SearchParams,
) -> tuple[int, list[sqlite3.Row]]:
    where, values = _meeting_where(params)
    total = connection.execute(
        f"SELECT COUNT(*) {MEETING_LIST_JOIN} {where}",
        values,
    ).fetchone()[0]
    rows = connection.execute(
        f"""
        SELECT
            meetings.id AS meeting_id,
            municipalities.prefecture AS prefecture,
            municipalities.name AS municipality,
            meetings.municipality_code AS municipality_code,
            meetings.session AS session,
            meetings.name AS name_of_meeting,
            meetings.date AS date,
            meetings.source_url AS meeting_url,
            meetings.pdf_url AS pdf_url
        {MEETING_LIST_JOIN}
        {where}
        ORDER BY meetings.date DESC, meetings.id ASC
        LIMIT ? OFFSET ?
        """,
        [*values, params.maximum_records, params.start_record - 1],
    ).fetchall()
    return total, rows


def meeting_speeches(connection: sqlite3.Connection, meeting_id: str) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT
            speeches.id AS speech_id,
            speeches.speech_order AS speech_order,
            speeches.speaker_name AS speaker,
            speeches.speaker_yomi AS speaker_yomi,
            speeches.speaker_group AS speaker_group,
            speeches.speaker_position AS speaker_position,
            speeches.speaker_role AS speaker_role,
            speeches.speech_text AS speech,
            speeches.start_page AS start_page,
            speeches.source_url AS speech_url
        FROM speeches
        WHERE speeches.meeting_id = ?
        ORDER BY speeches.speech_order ASC
        """,
        (meeting_id,),
    ).fetchall()


def matching_speech_summaries(
    connection: sqlite3.Connection,
    params: SearchParams,
    meeting_id: str,
) -> list[sqlite3.Row]:
    where, values = _speech_where(params, meeting_id=meeting_id)
    return connection.execute(
        f"""
        SELECT
            speeches.id AS speech_id,
            speeches.speech_order AS speech_order,
            speeches.speaker_name AS speaker
        {SPEECH_JOIN}
        {where}
        ORDER BY speeches.speech_order ASC
        """,
        values,
    ).fetchall()


def _meeting_where(params: SearchParams) -> tuple[str, list[object]]:
    clauses: list[str] = []
    values: list[object] = []
    _append_common_meeting_filters(params, clauses, values)
    if params.has_speech_condition():
        speech_where, speech_values = _speech_where(params)
        clauses.append(
            f"""meetings.id IN (
                SELECT speeches.meeting_id
                {SPEECH_JOIN}
                {speech_where}
            )"""
        )
        values.extend(speech_values)
    return _combine(clauses), values


def _speech_where(
    params: SearchParams,
    *,
    meeting_id: str | None = None,
) -> tuple[str, list[object]]:
    clauses: list[str] = []
    values: list[object] = []
    _append_common_meeting_filters(params, clauses, values)
    if meeting_id is not None:
        clauses.append("speeches.meeting_id = ?")
        values.append(meeting_id)
    if params.speech_id:
        clauses.append("speeches.id = ?")
        values.append(params.speech_id)
    if params.speech_number is not None:
        clauses.append("speeches.speech_order = ?")
        values.append(params.speech_number)
    _append_contains(clauses, values, "speeches.speaker_position", params.speaker_position)
    _append_contains(clauses, values, "speeches.speaker_group", params.speaker_group)
    _append_contains(clauses, values, "speeches.speaker_role", params.speaker_role)
    _append_and_likes(clauses, values, "speeches.speech_text", params.any_text)
    _append_or_likes(clauses, values, "speeches.speaker_name", params.speaker)
    return _combine(clauses), values


def _append_common_meeting_filters(
    params: SearchParams,
    clauses: list[str],
    values: list[object],
) -> None:
    _append_contains(clauses, values, "municipalities.prefecture", params.prefecture)
    _append_contains(clauses, values, "municipalities.name", params.municipality)
    if params.municipality_code:
        clauses.append("meetings.municipality_code = ?")
        values.append(params.municipality_code)
    _append_or_likes(clauses, values, "meetings.name", params.name_of_meeting)
    _append_contains(clauses, values, "meetings.session", params.session)
    if params.date_from is not None:
        clauses.append("meetings.date >= ?")
        values.append(params.date_from.isoformat())
    if params.date_until is not None:
        clauses.append("meetings.date <= ?")
        values.append(params.date_until.isoformat())
    if params.meeting_id:
        clauses.append("meetings.id = ?")
        values.append(params.meeting_id)


def _append_contains(
    clauses: list[str],
    values: list[object],
    column: str,
    raw: str | None,
) -> None:
    if not raw:
        return
    clauses.append(f"{column} LIKE ? ESCAPE '\\'")
    values.append(f"%{_escape_like(raw)}%")


def _append_and_likes(
    clauses: list[str],
    values: list[object],
    column: str,
    raw: str | None,
) -> None:
    terms = _split_terms(raw)
    for term in terms:
        clauses.append(f"{column} LIKE ? ESCAPE '\\'")
        values.append(f"%{_escape_like(term)}%")


def _append_or_likes(
    clauses: list[str],
    values: list[object],
    column: str,
    raw: str | None,
) -> None:
    terms = _split_terms(raw)
    if not terms:
        return
    if len(terms) == 1:
        clauses.append(f"{column} LIKE ? ESCAPE '\\'")
        values.append(f"%{_escape_like(terms[0])}%")
        return
    parts = " OR ".join(f"{column} LIKE ? ESCAPE '\\'" for _ in terms)
    clauses.append(f"({parts})")
    values.extend(f"%{_escape_like(term)}%" for term in terms)


def _split_terms(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part for part in raw.split(" ") if part]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _combine(clauses: list[str]) -> str:
    if not clauses:
        return ""
    return "WHERE " + " AND ".join(clauses)
