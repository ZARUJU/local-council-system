from datetime import datetime, timezone
from json import loads
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from local_council_system.collectors.state import (
    CollectionState,
    CollectionStateRepository,
    status_dir_for,
)

SCHEMA = Path(__file__).resolve().parents[1] / "config" / "data-repo" / "schema" / "collection-status.schema.json"


def test_status_dir_is_under_data_root(tmp_path: Path) -> None:
    assert status_dir_for(tmp_path / "canonical") == tmp_path / "canonical" / "status"


def test_repository_reads_and_writes_per_municipality_file(tmp_path: Path) -> None:
    repository = CollectionStateRepository(tmp_path / "status")
    assert repository.get("341002") is None
    synced = datetime(2026, 9, 14, 10, 0, tzinfo=timezone.utc)
    repository.save(
        CollectionState(municipality_code="341002", last_successful_sync=synced)
    )
    repository.save(
        CollectionState(
            municipality_code="281000",
            last_successful_sync=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
    )
    loaded = repository.get("341002")
    assert loaded is not None
    assert loaded.municipality_code == "341002"
    assert loaded.last_successful_sync == synced
    payload = loads((tmp_path / "status" / "341002.json").read_text(encoding="utf-8"))
    Draft202012Validator(
        loads(SCHEMA.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    ).validate(payload)
    assert (tmp_path / "status" / "281000.json").exists()
    assert repository.get("281000") is not None


def test_save_requires_last_successful_sync(tmp_path: Path) -> None:
    repository = CollectionStateRepository(tmp_path / "status")
    with pytest.raises(ValueError, match="last_successful_sync"):
        repository.save(
            CollectionState(municipality_code="341002", last_successful_sync=None)
        )
