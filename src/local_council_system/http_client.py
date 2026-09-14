from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse, parse_qsl, urlunparse

import httpx

logger = logging.getLogger(__name__)


def decode_html_bytes(data: bytes) -> str:
    for encoding in ("cp932", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("cp932", errors="replace")


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    # latin-1 のまま扱う。VOICES の TITL は Shift_JIS のパーセントエンコードで、
    # UTF-8 として読むと委員会ごとの一覧 URL が同じキャッシュキーに潰れる。
    query = urlencode(
        sorted(parse_qsl(parsed.query, keep_blank_values=True, encoding="latin-1")),
        encoding="latin-1",
    )
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            query,
            "",
        )
    )


class PoliteHttpClient:
    """Rate-limited HTTP GET with optional on-disk cache.

    Cache hits do not contact the origin. Live requests wait at least
    ``min_interval_seconds`` after the previous live request.
    """

    def __init__(
        self,
        *,
        user_agent: str,
        min_interval_seconds: float = 3.0,
        timeout_seconds: float = 30.0,
        cache_dir: Path | None = None,
        cache_enabled: bool = True,
    ) -> None:
        self._user_agent = user_agent
        self._min_interval = min_interval_seconds
        self._timeout = timeout_seconds
        self._cache_dir = cache_dir
        self._cache_enabled = cache_enabled and cache_dir is not None
        self._last_live_request_at = 0.0
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, url: str) -> Path:
        assert self._cache_dir is not None
        digest = hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()
        return self._cache_dir / f"{digest}.bin"

    def _read_cache(self, url: str) -> bytes | None:
        if not self._cache_enabled:
            return None
        path = self._cache_path(url)
        if path.exists():
            logger.info("http cache hit: %s", url)
            return path.read_bytes()
        return None

    def _write_cache(self, url: str, data: bytes) -> None:
        if not self._cache_enabled:
            return
        self._cache_path(url).write_bytes(data)

    def _wait_for_slot(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_live_request_at
        remaining = self._min_interval - elapsed
        if remaining > 0:
            logger.info("rate limit: waiting %.1fs", remaining)
            time.sleep(remaining)

    def get_bytes(self, url: str) -> bytes:
        cached = self._read_cache(url)
        if cached is not None:
            return cached
        self._wait_for_slot()
        logger.info("http GET %s", url)
        try:
            with httpx.Client(
                headers={"User-Agent": self._user_agent},
                timeout=self._timeout,
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.content
        finally:
            self._last_live_request_at = time.monotonic()
        self._write_cache(url, data)
        return data

    def get_text(self, url: str) -> str:
        return decode_html_bytes(self.get_bytes(url))


def join_url(base: str, path: str) -> str:
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))
