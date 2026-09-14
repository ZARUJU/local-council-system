from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaError

from local_council_system.validators.meeting import ValidationError

_PACKAGE_SCHEMA_DIR = Path(__file__).resolve().parents[3] / "config" / "data-repo" / "schema"
_FORMAT = FormatChecker()


def validate_meeting_payload(payload: dict[str, Any], *, schema_dir: Path | None = None) -> None:
    validator = _meeting_validator(schema_dir)
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        raise ValidationError(_format_errors(errors))


def validate_municipalities_payload(payload: dict[str, Any], *, schema_dir: Path | None = None) -> None:
    validator = _municipalities_validator(schema_dir)
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
    if errors:
        raise ValidationError(_format_errors(errors))


def schema_dir_for(data_root: Path | None) -> Path:
    if data_root is not None:
        candidate = data_root / "schema"
        if (candidate / "meeting.schema.json").exists():
            return candidate
    return _PACKAGE_SCHEMA_DIR


@lru_cache(maxsize=8)
def _load_schema(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _meeting_validator(schema_dir: Path | None) -> Draft202012Validator:
    directory = schema_dir or _PACKAGE_SCHEMA_DIR
    schema = _load_schema(str(directory / "meeting.schema.json"))
    return Draft202012Validator(schema, format_checker=_FORMAT)


def _municipalities_validator(schema_dir: Path | None) -> Draft202012Validator:
    directory = schema_dir or _PACKAGE_SCHEMA_DIR
    schema = _load_schema(str(directory / "municipalities.schema.json"))
    return Draft202012Validator(schema, format_checker=_FORMAT)


def _format_errors(errors: list[JsonSchemaError]) -> str:
    parts: list[str] = []
    for error in errors[:12]:
        location = ".".join(str(item) for item in error.path) or "$"
        parts.append(f"{location}: {error.message}")
    if len(errors) > 12:
        parts.append(f"... {len(errors) - 12} more")
    return "; ".join(parts)
