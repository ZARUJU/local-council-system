from datetime import date

from local_council_system.collectors.service import _assign_sequences
from local_council_system.models import MeetingReference


def _ref(source_id: str, day: date, name: str, issue: int) -> MeetingReference:
    return MeetingReference(
        municipality_code="341002",
        source_system="voices",
        source_meeting_id=source_id,
        url=f"https://example.test/{source_id}",
        discovered_date=day,
        name=name,
        issue=issue,
    )


def test_assign_sequences_reuses_existing_path() -> None:
    day = date(2025, 9, 17)
    plenary = _ref("5145", day, "本会議", 2)
    committee = _ref("5999", day, "総務委員会", 1)
    assigned = _assign_sequences(
        [committee, plenary],
        {"5145": 1},
        {"2025-09-17": {1}},
    )
    assert assigned["5145"] == 1
    assert assigned["5999"] == 2


def test_assign_sequences_fills_next_free_number() -> None:
    day = date(2025, 9, 17)
    first = _ref("100", day, "厚生委員会", 1)
    second = _ref("200", day, "本会議", 1)
    assigned = _assign_sequences([first, second], {}, {})
    assert assigned["100"] == 1
    assert assigned["200"] == 2
