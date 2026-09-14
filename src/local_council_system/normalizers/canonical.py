from __future__ import annotations

from local_council_system.ids import generate_meeting_id, generate_speech_id
from local_council_system.models import (
    CanonicalMeeting,
    CanonicalSpeaker,
    CanonicalSpeech,
    ParsedMeeting,
    ParsedSpeaker,
)

SCHEMA_VERSION = "1.0"


def to_canonical(
    parsed: ParsedMeeting,
    *,
    municipality_code: str,
    source_system: str,
) -> CanonicalMeeting:
    meeting_id = generate_meeting_id(
        municipality_code,
        source_system,
        parsed.source_meeting_id,
    )
    speeches = tuple(
        CanonicalSpeech(
            id=str(
                generate_speech_id(
                    meeting_id,
                    source_speech_id=speech.source_speech_id,
                    speech_number=None,
                    speech_order=speech.order,
                )
            ),
            order=speech.order,
            source_identity={"speechId": speech.source_speech_id},
            speaker=_speaker(speech.speaker),
            text=speech.text,
            start_page=speech.start_page,
            source_url=speech.source_url,
        )
        for speech in parsed.speeches
    )
    return CanonicalMeeting(
        schema_version=SCHEMA_VERSION,
        id=str(meeting_id),
        municipality_code=municipality_code,
        source_identity={
            "system": source_system,
            "meetingId": parsed.source_meeting_id,
        },
        session=parsed.session,
        name=parsed.name,
        date=parsed.date.isoformat(),
        issue=parsed.issue,
        speeches=speeches,
        source_url=parsed.source_url,
        pdf_url=parsed.pdf_url,
    )


def _speaker(speaker: ParsedSpeaker) -> CanonicalSpeaker:
    return CanonicalSpeaker(
        name=speaker.name,
        yomi=speaker.yomi,
        group=speaker.group,
        position=speaker.position,
        role=speaker.role,
    )
