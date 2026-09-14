from __future__ import annotations

from contextlib import closing
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from local_council_system.api.search import (
    SearchParams,
    matching_speech_summaries,
    meeting_speeches,
    open_readonly,
    search_meetings,
    search_speeches,
)

CONTENT_TYPE = "application/json; charset=utf-8"


def create_app(database: Path) -> FastAPI:
    app = FastAPI(title="local-council-system", version="0.1.0")
    app.state.database = database.resolve()

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [str(error["msg"]) for error in exc.errors()]
        return _error("Invalid request.", details, 400)

    @app.exception_handler(HTTPException)
    async def _http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, dict) and "message" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        message = str(detail) if detail else "Invalid request."
        return _error(message, [message], exc.status_code)

    @app.get("/api/speech")
    def speech_endpoint(
        startRecord: int = Query(1),
        maximumRecords: int = Query(30),
        prefecture: str | None = None,
        municipality: str | None = None,
        municipalityCode: str | None = None,
        nameOfMeeting: str | None = None,
        session: str | None = None,
        any: str | None = None,
        speaker: str | None = None,
        from_: date | None = Query(None, alias="from"),
        until: date | None = None,
        speechNumber: int | None = None,
        speakerPosition: str | None = None,
        speakerGroup: str | None = None,
        speakerRole: str | None = None,
        speechID: str | None = None,
        meetingID: str | None = None,
    ) -> JSONResponse:
        params = _params(
            startRecord,
            maximumRecords,
            maximum_max=100,
            default_max=30,
            prefecture=prefecture,
            municipality=municipality,
            municipality_code=municipalityCode,
            name_of_meeting=nameOfMeeting,
            session=session,
            any_text=any,
            speaker=speaker,
            date_from=from_,
            date_until=until,
            speech_number=speechNumber,
            speaker_position=speakerPosition,
            speaker_group=speakerGroup,
            speaker_role=speakerRole,
            speech_id=speechID,
            meeting_id=meetingID,
        )
        with closing(_connect(app)) as connection:
            total, rows = search_speeches(connection, params)
        records = [_speech_record(row) for row in rows]
        return _ok(
            {
                "numberOfRecords": total,
                "numberOfReturn": len(records),
                "startRecord": params.start_record,
                "nextRecordPosition": _next_position(params, total, len(records)),
                "speechRecord": records,
            }
        )

    @app.get("/api/meeting_list")
    def meeting_list_endpoint(
        startRecord: int = Query(1),
        maximumRecords: int = Query(30),
        prefecture: str | None = None,
        municipality: str | None = None,
        municipalityCode: str | None = None,
        nameOfMeeting: str | None = None,
        session: str | None = None,
        any: str | None = None,
        speaker: str | None = None,
        from_: date | None = Query(None, alias="from"),
        until: date | None = None,
        speechNumber: int | None = None,
        speakerPosition: str | None = None,
        speakerGroup: str | None = None,
        speakerRole: str | None = None,
        speechID: str | None = None,
        meetingID: str | None = None,
    ) -> JSONResponse:
        params = _params(
            startRecord,
            maximumRecords,
            maximum_max=100,
            default_max=30,
            prefecture=prefecture,
            municipality=municipality,
            municipality_code=municipalityCode,
            name_of_meeting=nameOfMeeting,
            session=session,
            any_text=any,
            speaker=speaker,
            date_from=from_,
            date_until=until,
            speech_number=speechNumber,
            speaker_position=speakerPosition,
            speaker_group=speakerGroup,
            speaker_role=speakerRole,
            speech_id=speechID,
            meeting_id=meetingID,
        )
        connection = _connect(app)
        with closing(connection):
            total, rows = search_meetings(connection, params)
            records = []
            for row in rows:
                item = _meeting_base(row)
                if params.has_speech_condition():
                    item["speechRecord"] = [
                        {
                            "speechID": speech["speech_id"],
                            "speechOrder": speech["speech_order"],
                            "speaker": speech["speaker"],
                        }
                        for speech in matching_speech_summaries(connection, params, row["meeting_id"])
                    ]
                records.append(item)
        return _ok(
            {
                "numberOfRecords": total,
                "numberOfReturn": len(records),
                "startRecord": params.start_record,
                "nextRecordPosition": _next_position(params, total, len(records)),
                "meetingRecord": records,
            }
        )

    @app.get("/api/meeting")
    def meeting_endpoint(
        startRecord: int = Query(1),
        maximumRecords: int = Query(3),
        prefecture: str | None = None,
        municipality: str | None = None,
        municipalityCode: str | None = None,
        nameOfMeeting: str | None = None,
        session: str | None = None,
        any: str | None = None,
        speaker: str | None = None,
        from_: date | None = Query(None, alias="from"),
        until: date | None = None,
        speechNumber: int | None = None,
        speakerPosition: str | None = None,
        speakerGroup: str | None = None,
        speakerRole: str | None = None,
        speechID: str | None = None,
        meetingID: str | None = None,
    ) -> JSONResponse:
        params = _params(
            startRecord,
            maximumRecords,
            maximum_max=10,
            default_max=3,
            prefecture=prefecture,
            municipality=municipality,
            municipality_code=municipalityCode,
            name_of_meeting=nameOfMeeting,
            session=session,
            any_text=any,
            speaker=speaker,
            date_from=from_,
            date_until=until,
            speech_number=speechNumber,
            speaker_position=speakerPosition,
            speaker_group=speakerGroup,
            speaker_role=speakerRole,
            speech_id=speechID,
            meeting_id=meetingID,
        )
        connection = _connect(app)
        with closing(connection):
            total, rows = search_meetings(connection, params)
            records = []
            for row in rows:
                item = _meeting_base(row)
                item["speechRecord"] = [
                    {
                        "speechID": speech["speech_id"],
                        "speechOrder": speech["speech_order"],
                        "speaker": speech["speaker"],
                        "speakerYomi": speech["speaker_yomi"],
                        "speakerGroup": speech["speaker_group"],
                        "speakerPosition": speech["speaker_position"],
                        "speakerRole": speech["speaker_role"],
                        "speech": speech["speech"],
                        "startPage": speech["start_page"],
                        "speechURL": speech["speech_url"],
                    }
                    for speech in meeting_speeches(connection, row["meeting_id"])
                ]
                records.append(item)
        return _ok(
            {
                "numberOfRecords": total,
                "numberOfReturn": len(records),
                "startRecord": params.start_record,
                "nextRecordPosition": _next_position(params, total, len(records)),
                "meetingRecord": records,
            }
        )

    return app


def _connect(app: FastAPI):
    database: Path = app.state.database
    if not database.exists():
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Search database is unavailable.",
                "details": [f"missing {database}"],
            },
        )
    return open_readonly(database)


def _params(
    start_record: int,
    maximum_records: int,
    *,
    maximum_max: int,
    default_max: int,
    **filters: Any,
) -> SearchParams:
    if start_record < 1:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid request.",
                "details": ["startRecord must be 1 or greater."],
            },
        )
    if maximum_records < 1 or maximum_records > maximum_max:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid request.",
                "details": [f"maximumRecords must be between 1 and {maximum_max}."],
            },
        )
    params = SearchParams(
        start_record=start_record,
        maximum_records=maximum_records or default_max,
        prefecture=filters.get("prefecture"),
        municipality=filters.get("municipality"),
        municipality_code=filters.get("municipality_code"),
        name_of_meeting=filters.get("name_of_meeting"),
        session=filters.get("session"),
        any_text=filters.get("any_text"),
        speaker=filters.get("speaker"),
        date_from=filters.get("date_from"),
        date_until=filters.get("date_until"),
        speech_number=filters.get("speech_number"),
        speaker_position=filters.get("speaker_position"),
        speaker_group=filters.get("speaker_group"),
        speaker_role=filters.get("speaker_role"),
        speech_id=filters.get("speech_id"),
        meeting_id=filters.get("meeting_id"),
    )
    if not params.has_search_condition():
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid request.",
                "details": ["at least one search condition is required."],
            },
        )
    return params


def _speech_record(row: Any) -> dict[str, Any]:
    return {
        "speechID": row["speech_id"],
        "meetingID": row["meeting_id"],
        "prefecture": row["prefecture"],
        "municipality": row["municipality"],
        "municipalityCode": row["municipality_code"],
        "session": row["session"],
        "nameOfMeeting": row["name_of_meeting"],
        "date": row["date"],
        "speechOrder": row["speech_order"],
        "speaker": row["speaker"],
        "speakerYomi": row["speaker_yomi"],
        "speakerGroup": row["speaker_group"],
        "speakerPosition": row["speaker_position"],
        "speakerRole": row["speaker_role"],
        "speech": row["speech"],
        "startPage": row["start_page"],
        "speechURL": row["speech_url"],
        "meetingURL": row["meeting_url"],
        "pdfURL": row["pdf_url"],
    }


def _meeting_base(row: Any) -> dict[str, Any]:
    return {
        "meetingID": row["meeting_id"],
        "prefecture": row["prefecture"],
        "municipality": row["municipality"],
        "municipalityCode": row["municipality_code"],
        "session": row["session"],
        "nameOfMeeting": row["name_of_meeting"],
        "date": row["date"],
        "meetingURL": row["meeting_url"],
        "pdfURL": row["pdf_url"],
    }


def _next_position(params: SearchParams, total: int, returned: int) -> int | None:
    nxt = params.start_record + returned
    if returned == 0 or nxt > total:
        return None
    return nxt


def _ok(payload: dict[str, Any]) -> JSONResponse:
    return JSONResponse(content=jsonable_encoder(payload), media_type=CONTENT_TYPE)


def _error(message: str, details: list[str], status: int) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"message": message, "details": details},
        media_type=CONTENT_TYPE,
    )


app = create_app(Path("var/search.sqlite"))
