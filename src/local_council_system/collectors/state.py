from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

STATUS_DIRNAME = "status"
SCHEMA_VERSION = "1.0"
INDENT = 2


@dataclass
class CollectionState:
    municipality_code: str
    last_successful_sync: datetime | None


class CollectionStateRepository:
    """data リポジトリの status/{municipalityCode}.json を読み書きする。"""

    def __init__(self, status_dir: Path) -> None:
        self._status_dir = status_dir

    def get(self, municipality_code: str) -> CollectionState | None:
        path = self.path_for(municipality_code)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: JSON root must be an object")
        code = payload.get("municipalityCode")
        if code != municipality_code:
            raise ValueError(
                f"{path}: municipalityCode {code!r} does not match {municipality_code!r}"
            )
        raw = payload.get("lastSuccessfulSync")
        if not raw:
            return CollectionState(
                municipality_code=municipality_code,
                last_successful_sync=None,
            )
        synced = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return CollectionState(
            municipality_code=municipality_code,
            last_successful_sync=synced,
        )

    def save(self, state: CollectionState) -> None:
        if state.last_successful_sync is None:
            raise ValueError("last_successful_sync is required to save collection status")
        path = self.path_for(state.municipality_code)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(_serialize(state), ensure_ascii=False, indent=INDENT) + "\n"
        path.write_text(text, encoding="utf-8", newline="\n")

    def path_for(self, municipality_code: str) -> Path:
        return self._status_dir / f"{municipality_code}.json"


def status_dir_for(data_root: Path) -> Path:
    return data_root / STATUS_DIRNAME


def _serialize(state: CollectionState) -> dict:
    synced = state.last_successful_sync
    if synced is None:
        raise ValueError("last_successful_sync is required to serialize collection status")
    if synced.tzinfo is None:
        synced = synced.replace(tzinfo=timezone.utc)
    return {
        "schemaVersion": SCHEMA_VERSION,
        "municipalityCode": state.municipality_code,
        "lastSuccessfulSync": synced.astimezone(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }
