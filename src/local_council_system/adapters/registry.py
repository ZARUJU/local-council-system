from __future__ import annotations

from local_council_system.adapters.base import MinutesAdapter
from local_council_system.adapters.hiroshima_voices import HiroshimaVoicesAdapter
from local_council_system.adapters.kobe_dbsr import KobeDbsrAdapter
from local_council_system.config import SourceConfig
from local_council_system.http_client import PoliteHttpClient

ADAPTERS: dict[str, type[MinutesAdapter]] = {
    "hiroshima-voices": HiroshimaVoicesAdapter,
    "kobe-dbsr": KobeDbsrAdapter,
}


def create_adapter(config: SourceConfig, http: PoliteHttpClient) -> MinutesAdapter:
    adapter_cls = ADAPTERS.get(config.adapter)
    if adapter_cls is None:
        supported = ", ".join(sorted(ADAPTERS))
        raise ValueError(f"unsupported adapter: {config.adapter} (supported: {supported})")
    return adapter_cls(config, http)
