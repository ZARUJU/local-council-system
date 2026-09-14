from __future__ import annotations

import json
import shutil
from pathlib import Path

from local_council_system.config import SourceConfig

SCHEMA_VERSION = "1.0"
INDENT = 2

_PACKAGE_DATA_REPO = Path(__file__).resolve().parents[3] / "config" / "data-repo"


def ensure_data_repo_layout(data_root: Path, config: SourceConfig) -> None:
    """data リポジトリと同じ配置（schema / master / data）を data_root に揃える。

    status/ は同期成功時だけ Collector が書く。ここでは作らない。
    """
    _copy_schemas(data_root)
    upsert_municipality_master(data_root, config)


def _copy_schemas(data_root: Path) -> None:
    source = _PACKAGE_DATA_REPO / "schema"
    if not source.exists():
        return
    destination = data_root / "schema"
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(source.glob("*.json")):
        shutil.copyfile(path, destination / path.name)


def upsert_municipality_master(data_root: Path, config: SourceConfig) -> None:
    path = data_root / "master" / "municipalities.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    records = _load_municipalities(path)
    records = [item for item in records if item.get("code") != config.municipality_code]
    records.append(
        {
            "code": config.municipality_code,
            "name": config.municipality_name,
            "prefecture": config.prefecture,
        }
    )
    records.sort(key=lambda item: str(item.get("code") or ""))
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "municipalities": records,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=INDENT) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    path.write_text(text, encoding="utf-8", newline="\n")


def _load_municipalities(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    records = payload.get("municipalities")
    if not isinstance(records, list):
        return []
    return [item for item in records if isinstance(item, dict)]
