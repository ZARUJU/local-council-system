from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class HttpConfig:
    min_interval_seconds: float = 3.0
    timeout_seconds: float = 30.0
    cache: bool = True
    user_agent: str = (
        "local-council-system/0.1 "
        "(local council minutes collector; polite; 1 request / 3s)"
    )


@dataclass(frozen=True)
class CollectionConfig:
    initial_from: date | None
    lookback_days: int = 30
    earliest_year: int = 2025


@dataclass(frozen=True)
class SourceConfig:
    municipality_code: str
    municipality_name: str
    prefecture: str
    adapter: str
    source_system: str
    base_url: str
    minutes_base_url: str
    tenant_id: str | None
    tenant_slug: str | None
    listing_path: str
    query_type: str
    cabinets: tuple[int, ...]
    collection: CollectionConfig
    http: HttpConfig
    export_root: Path


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def load_source_config(path: Path) -> SourceConfig:
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    source = raw.get("source") or {}
    collection = raw.get("collection") or {}
    http = raw.get("http") or {}
    export = raw.get("export") or {}
    cabinets = source.get("cabinets") or [1]
    return SourceConfig(
        municipality_code=str(raw["municipalityCode"]),
        municipality_name=str(raw.get("municipalityName") or ""),
        prefecture=str(raw.get("prefecture") or ""),
        adapter=str(raw["adapter"]),
        source_system=str(source.get("system") or "voices"),
        base_url=str(source["baseUrl"]).rstrip("/"),
        minutes_base_url=str(source["minutesBaseUrl"]).rstrip("/"),
        tenant_id=str(source["tenantId"]) if source.get("tenantId") not in (None, "") else None,
        tenant_slug=str(source["tenantSlug"]) if source.get("tenantSlug") not in (None, "") else None,
        listing_path=str(source.get("listingPath") or "/100000"),
        query_type=str(source.get("queryType") or "new"),
        cabinets=tuple(int(item) for item in cabinets),
        collection=CollectionConfig(
            initial_from=_parse_date(collection.get("initialFrom")),
            lookback_days=int(collection.get("lookbackDays") or 30),
            earliest_year=int(collection.get("earliestYear") or 2025),
        ),
        http=HttpConfig(
            min_interval_seconds=float(http.get("minIntervalSeconds") or 3.0),
            timeout_seconds=float(http.get("timeoutSeconds") or 30.0),
            cache=bool(http.get("cache", True)),
            user_agent=str(http.get("userAgent") or HttpConfig.user_agent),
        ),
        export_root=_resolve_export_root(
            export.get("dataRoot") or "var/canonical",
            config_path=path,
        ),
    )


def default_config_dir() -> Path:
    candidates = [
        Path.cwd() / "config" / "sources",
        Path(__file__).resolve().parents[2] / "config" / "sources",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _resolve_export_root(raw: str, *, config_path: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    repo_root = config_path.resolve().parents[2]
    return (repo_root / path).resolve()


def load_municipality_config(municipality_code: str, config_dir: Path | None = None) -> SourceConfig:
    directory = config_dir or default_config_dir()
    path = directory / f"{municipality_code}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"source config not found: {path}")
    return load_source_config(path)
