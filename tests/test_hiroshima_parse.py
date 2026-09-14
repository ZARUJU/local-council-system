from datetime import date

from local_council_system.exporters.json_exporter import dumps_canonical
from local_council_system.models import MeetingReference
from local_council_system.normalizers.canonical import to_canonical
from local_council_system.parsers.hiroshima_voices import parse_meeting_html
from local_council_system.validators.meeting import validate_meeting


def _reference() -> MeetingReference:
    return MeetingReference(
        municipality_code="341002",
        source_system="voices",
        source_meeting_id="5145",
        url="https://hiroshima.gijiroku.com/voices/cgi/voiweb.exe?ACT=200&FINO=5145",
        discovered_date=date(2025, 9, 17),
        title_hint="令和７年第３回９月定例会 09月17日-02号",
        session="令和　７年第　３回　９月定例会",
        name="本会議",
        issue=2,
        fetch_url=(
            "https://hiroshima.gijiroku.com/voices/cgi/voiweb.exe"
            "?ACT=203&FINO=5145&HATSUGENMODE=1&HYOUJIMODE=0&STYLE=0"
        ),
    )


def test_parse_2025_09_17_speeches(meeting_html: str) -> None:
    parsed = parse_meeting_html(meeting_html, _reference())
    assert parsed.date == date(2025, 9, 17)
    assert parsed.issue == 2
    assert parsed.name == "本会議"
    assert len(parsed.speeches) == 145
    assert parsed.speeches[0].source_speech_id == "394548"
    assert parsed.speeches[-1].source_speech_id == "394692"

    yamaji = next(
        speech
        for speech in parsed.speeches
        if speech.speaker.name == "山路英男"
    )
    assert yamaji.speaker.position == "議員"
    assert yamaji.source_speech_id == "394555"
    assert "一般質問をさせていただきます" in yamaji.text

    header = parsed.speeches[0]
    assert header.speaker.name == "（会議録冒頭）"
    assert header.speaker.role == "議事"

    last = parsed.speeches[-1]
    assert "function get_view_no" not in last.text
    assert "parseInt" not in last.text

    agenda = next(speech for speech in parsed.speeches if speech.speaker.role == "議事" and "一般質問" in speech.speaker.name)
    assert "一般質問" in agenda.text

    mayor = next(
        speech
        for speech in parsed.speeches
        if speech.speaker.name == "松井一實"
    )
    assert mayor.speaker.position == "市長"


def test_canonical_roundtrip_is_valid_and_stable(meeting_html: str) -> None:
    parsed = parse_meeting_html(meeting_html, _reference())
    canonical = to_canonical(
        parsed,
        municipality_code="341002",
        source_system="voices",
    )
    validate_meeting(canonical)
    dumped = dumps_canonical(canonical)
    assert dumps_canonical(canonical) == dumped
    assert canonical.source_identity == {"system": "voices", "meetingId": "5145"}
    assert canonical.session == "令和７年第３回９月定例会"
    assert canonical.id == "931380eb-f008-5aae-8c28-3d4180700c35"
    assert canonical.speeches[7].id == "5e583702-a478-5119-abca-fc58977510f8"
    assert canonical.speeches[7].source_identity["speechId"] == "394555"
    assert '"schemaVersion": "1.0"' in dumped
    assert dumped.endswith("\n")


def test_committee_report_uses_member_pattern() -> None:
    html = (
        '<A NAME="HUID396935"></A>'
        "◎43番（山路英男議員）　決算特別委員会に付託されました。<BR>"
        "本文です。"
    )
    parsed = parse_meeting_html(html, _reference())
    assert parsed.speeches[0].speaker.name == "山路英男"
    assert parsed.speeches[0].speaker.position == "議員"
    assert parsed.speeches[0].text.startswith("決算特別委員会に付託されました。")


def test_parse_soumu_committee_2025_07_25(soumu_meeting_html: str) -> None:
    reference = MeetingReference(
        municipality_code="341002",
        source_system="voices",
        source_meeting_id="5137",
        url="https://hiroshima.gijiroku.com/voices/cgi/voiweb.exe?ACT=200&FINO=5137",
        discovered_date=date(2025, 7, 25),
        title_hint="令和７年７月２５日総務委員会 07月25日-01号",
        session="令和７年７月２５日",
        name="総務委員会",
        issue=1,
        fetch_url=(
            "https://hiroshima.gijiroku.com/voices/cgi/voiweb.exe"
            "?ACT=203&FINO=5137&HATSUGENMODE=1&HYOUJIMODE=0&STYLE=0"
        ),
    )
    parsed = parse_meeting_html(soumu_meeting_html, reference)
    assert parsed.name == "総務委員会"
    assert parsed.session == "令和７年７月２５日"
    assert len(parsed.speeches) == 36
    assert parsed.speeches[0].speaker.name == "（会議録冒頭）"
    chair = parsed.speeches[1]
    assert chair.speaker.name == "川本"
    assert chair.speaker.position == "委員長"
    assert chair.text.startswith("ただいまから、総務委員会を開会いたします。")
    mayor = next(speech for speech in parsed.speeches if speech.speaker.position == "市長")
    assert mayor.speaker.name == "松井"
    member = next(speech for speech in parsed.speeches if speech.speaker.position == "委員")
    assert member.speaker.name == "中村"
    last = parsed.speeches[-1]
    assert "function get_view_no" not in last.text
    assert "parseInt" not in last.text
