from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from local_council_system.validators.meeting import ValidationError
from local_council_system.validators.schema import (
    schema_dir_for,
    validate_meeting_payload,
    validate_municipalities_payload,
)

logger = logging.getLogger(__name__)

SCHEMA_SQL = (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")
MEETING_FILE_GLOB = "data/*/*/*/*.json"


@dataclass(frozen=True)
class BuildResult:
    municipalities: int
    meetings: int
    speeches: int
    output: Path


def build_search_database(data_root: Path, output: Path) -> BuildResult:
    data_root = data_root.resolve()
    output = output.resolve()
    if not data_root.exists():
        raise FileNotFoundError(f"data root not found: {data_root}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f"{output.name}.new")
    if temporary.exists():
        temporary.unlink()

    schema_dir = schema_dir_for(data_root)
    municipalities = _load_municipalities(data_root, schema_dir)
    meetings = _iter_meeting_files(data_root)

    connection = sqlite3.connect(temporary)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA_SQL)
        _insert_municipalities(connection, municipalities)
        meeting_count = 0
        speech_count = 0
        known_codes = {item["code"] for item in municipalities}
        for path in meetings:
            payload = _load_json(path)
            validate_meeting_payload(payload, schema_dir=schema_dir)
            meeting = payload["meeting"]
            code = meeting["municipalityCode"]
            if code not in known_codes:
                raise ValidationError(f"{path}: unknown municipalityCode {code}")
            _insert_meeting(connection, payload)
            meeting_count += 1
            speech_count += len(payload["speeches"])
        leftover = connection.execute("PRAGMA foreign_key_check").fetchall()
        if leftover:
            raise ValidationError(f"foreign key check failed: {leftover[:5]}")
        connection.commit()
    except Exception:
        connection.close()
        if temporary.exists():
            temporary.unlink()
        raise
    connection.close()
    os.replace(temporary, output)
    logger.info(
        "build-db municipalities=%s meetings=%s speeches=%s output=%s",
        len(municipalities),
        meeting_count,
        speech_count,
        output,
    )
    return BuildResult(
        municipalities=len(municipalities),
        meetings=meeting_count,
        speeches=speech_count,
        output=output,
    )


def _load_municipalities(data_root: Path, schema_dir: Path) -> list[dict[str, Any]]:
    path = data_root / "master" / "municipalities.json"
    if not path.exists():
        raise FileNotFoundError(f"municipality master not found: {path}")
    payload = _load_json(path)
    validate_municipalities_payload(payload, schema_dir=schema_dir)
    records = payload["municipalities"]
    if not records:
        raise ValidationError("municipalities master is empty")
    return records


def _iter_meeting_files(data_root: Path) -> list[Path]:
    return sorted(path for path in data_root.glob(MEETING_FILE_GLOB) if path.is_file())


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(payload, dict):
        raise ValidationError(f"{path}: JSON root must be an object")
    return payload


def _insert_municipalities(connection: sqlite3.Connection, records: list[dict[str, Any]]) -> None:
    connection.executemany(
        "INSERT INTO municipalities(code, name, prefecture) VALUES (?, ?, ?)",
        [(item["code"], item["name"], item["prefecture"]) for item in records],
    )


def _insert_meeting(connection: sqlite3.Connection, payload: dict[str, Any]) -> None:
    meeting = payload["meeting"]
    source = payload["source"]
    connection.execute(
        """
        INSERT INTO meetings(
            id, municipality_code, session, name, date, issue, source_url, pdf_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            meeting["id"],
            meeting["municipalityCode"],
            meeting["session"],
            meeting["name"],
            meeting["date"],
            meeting["issue"],
            source["url"],
            source["pdfURL"],
        ),
    )
    rows = [
        (
            speech["id"],
            meeting["id"],
            speech["order"],
            speech["speaker"]["name"],
            speech["speaker"]["yomi"],
            speech["speaker"]["group"],
            speech["speaker"]["position"],
            speech["speaker"]["role"],
            speech["text"],
            speech["startPage"],
            speech["sourceURL"],
        )
        for speech in payload["speeches"]
    ]
    connection.executemany(
        """
        INSERT INTO speeches(
            id, meeting_id, speech_order, speaker_name, speaker_yomi,
            speaker_group, speaker_position, speaker_role, speech_text,
            start_page, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
