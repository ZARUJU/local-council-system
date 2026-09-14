from __future__ import annotations

from local_council_system.models import CanonicalMeeting


class ValidationError(ValueError):
    pass


def validate_meeting(meeting: CanonicalMeeting) -> None:
    errors: list[str] = []
    if not meeting.id:
        errors.append("meeting.id is required")
    if not meeting.municipality_code:
        errors.append("meeting.municipalityCode is required")
    if not meeting.date:
        errors.append("meeting.date is required")
    if not meeting.name:
        errors.append("meeting.name is required")
    if not meeting.source_url:
        errors.append("source.url is required")
    if not meeting.speeches:
        errors.append("speeches must not be empty")

    orders: set[int] = set()
    ids: set[str] = set()
    for speech in meeting.speeches:
        if not speech.id:
            errors.append(f"speech.order={speech.order} missing id")
        if speech.id in ids:
            errors.append(f"duplicate speech.id {speech.id}")
        ids.add(speech.id)
        if speech.order in orders:
            errors.append(f"duplicate speech.order {speech.order}")
        orders.add(speech.order)
        if not speech.speaker.name:
            errors.append(f"speech.order={speech.order} missing speaker.name")
        if speech.text is None or speech.text == "":
            errors.append(f"speech.order={speech.order} missing text")

    if errors:
        raise ValidationError("; ".join(errors))
