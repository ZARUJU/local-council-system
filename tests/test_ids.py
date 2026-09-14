from local_council_system.ids import (
    MEETING_NAMESPACE,
    generate_meeting_id,
    generate_speech_id,
    meeting_identity,
)


def test_meeting_identity_format() -> None:
    assert meeting_identity("341002", "voices", "5145") == "341002:voices:5145"


def test_meeting_id_is_deterministic() -> None:
    first = generate_meeting_id("341002", "voices", "5145")
    second = generate_meeting_id("341002", "voices", "5145")
    assert first == second
    assert first.version == 5
    assert str(first) == "931380eb-f008-5aae-8c28-3d4180700c35"


def test_speech_id_prefers_source_id() -> None:
    meeting_id = generate_meeting_id("341002", "voices", "5145")
    first = generate_speech_id(
        meeting_id,
        source_speech_id="394555",
        speech_number=None,
        speech_order=8,
    )
    second = generate_speech_id(
        meeting_id,
        source_speech_id="394555",
        speech_number=None,
        speech_order=99,
    )
    assert first == second
    assert first.version == 5


def test_namespace_is_fixed() -> None:
    assert str(MEETING_NAMESPACE) == "3c13f2d9-8cc8-4ae1-81a6-a757ec6caaa4"
