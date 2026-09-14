from uuid import UUID, uuid5

# プロジェクト固定の Meeting namespace。公開後は変更しない。
MEETING_NAMESPACE = UUID("3c13f2d9-8cc8-4ae1-81a6-a757ec6caaa4")


def generate_meeting_id(
    municipality_code: str,
    source_system: str,
    source_meeting_id: str,
) -> UUID:
    identity = f"{municipality_code}:{source_system}:{source_meeting_id}"
    return uuid5(MEETING_NAMESPACE, identity)


def generate_speech_id(
    meeting_id: UUID,
    *,
    source_speech_id: str | None,
    speech_number: int | None,
    speech_order: int,
) -> UUID:
    if source_speech_id is not None:
        identity = f"source:{source_speech_id}"
    elif speech_number is not None:
        identity = f"number:{speech_number}"
    else:
        identity = f"order:{speech_order}"
    return uuid5(meeting_id, identity)


def meeting_identity(
    municipality_code: str,
    source_system: str,
    source_meeting_id: str,
) -> str:
    return f"{municipality_code}:{source_system}:{source_meeting_id}"
