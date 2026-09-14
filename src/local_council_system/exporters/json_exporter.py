from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from local_council_system.models import CanonicalMeeting, CanonicalSpeaker, CanonicalSpeech

INDENT = "  "
MEETING_FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(\d{3})\.json$")


def meeting_path(
    data_root: Path,
    municipality_code: str,
    meeting_date: str,
    sequence: int,
) -> Path:
    prefecture_code = municipality_code[:2]
    year = meeting_date[:4]
    filename = f"{meeting_date}-{sequence:03d}.json"
    return data_root / "data" / prefecture_code / municipality_code / year / filename


def canonical_to_dict(meeting: CanonicalMeeting) -> dict:
    return {
        "schemaVersion": meeting.schema_version,
        "meeting": {
            "id": meeting.id,
            "municipalityCode": meeting.municipality_code,
            "sourceIdentity": {
                "system": meeting.source_identity["system"],
                "meetingId": meeting.source_identity["meetingId"],
            },
            "session": meeting.session,
            "name": meeting.name,
            "date": meeting.date,
            "issue": meeting.issue,
        },
        "speeches": [_speech_to_dict(speech) for speech in meeting.speeches],
        "source": {
            "url": meeting.source_url,
            "pdfURL": meeting.pdf_url,
        },
    }


def _speech_to_dict(speech: CanonicalSpeech) -> dict:
    return {
        "id": speech.id,
        "order": speech.order,
        "sourceIdentity": {
            "speechId": speech.source_identity.get("speechId"),
        },
        "speaker": _speaker_to_dict(speech.speaker),
        "text": speech.text,
        "startPage": speech.start_page,
        "sourceURL": speech.source_url,
    }


def _speaker_to_dict(speaker: CanonicalSpeaker) -> dict:
    return {
        "name": speaker.name,
        "yomi": speaker.yomi,
        "group": speaker.group,
        "position": speaker.position,
        "role": speaker.role,
    }


def dumps_canonical(meeting: CanonicalMeeting) -> str:
    payload = canonical_to_dict(meeting)
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def export_meeting(
    meeting: CanonicalMeeting,
    path: Path,
) -> bool:
    """Write Canonical JSON. Returns True if the file content changed."""
    text = dumps_canonical(meeting)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def load_existing_sequences(
    data_root: Path,
    municipality_code: str,
) -> tuple[dict[str, int], dict[str, set[int]]]:
    """既存 Canonical JSON から source meetingId → 同日連番を読む。

    戻り値は (meetingId → sequence, 開催日 → 使用済み sequence)。
    一度書いたパスを後からずらさないために使う。
    """
    by_source: dict[str, int] = {}
    used: dict[str, set[int]] = defaultdict(set)
    prefecture_code = municipality_code[:2]
    base = data_root / "data" / prefecture_code / municipality_code
    if not base.exists():
        return by_source, used
    for path in sorted(base.glob("*/*.json")):
        match = MEETING_FILE_RE.match(path.name)
        if match is None:
            continue
        meeting_date = match.group(1)
        sequence = int(match.group(2))
        used[meeting_date].add(sequence)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meeting = payload.get("meeting") if isinstance(payload, dict) else None
        identity = meeting.get("sourceIdentity") if isinstance(meeting, dict) else None
        source_id = identity.get("meetingId") if isinstance(identity, dict) else None
        if isinstance(source_id, str) and source_id:
            by_source[source_id] = sequence
    return by_source, used
