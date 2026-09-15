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
        self._client = httpx.Client(
            headers={"User-Agent": self._user_agent},
            timeout=self._timeout,
            follow_redirects=True,
        )
        if self._cache_dir is not None:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        self._client.close()

    def _cache_path(self, key: str) -> Path:
        assert self._cache_dir is not None
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self._cache_dir / f"{digest}.bin"

    def _read_cache(self, key: str, log_url: str) -> bytes | None:
        if not self._cache_enabled:
            return None
        path = self._cache_path(key)
        if path.exists():
            logger.info("http cache hit: %s", log_url)
            return path.read_bytes()
        return None

    def _write_cache(self, key: str, data: bytes) -> None:
        if not self._cache_enabled:
            return
        self._cache_path(key).write_bytes(data)

    def _cacheable(self, url: str) -> bool:
        # dbsr の一覧はビューア ID がセッションに紐づく。キャッシュすると 2 ページ目が別検索になる。
        parsed = urlparse(url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if query.get("Template") == "list":
            return False
        # kensakusystem の See.exe は Code が閲覧セッション。古い応答を再利用しない。
        if parsed.path.endswith("See.exe"):
            return False
        return True

    def _use_cache(self, url: str, cache: bool | None) -> bool:
        if cache is False:
            return False
        return self._cacheable(url)

    def _wait_for_slot(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_live_request_at
        remaining = self._min_interval - elapsed
        if remaining > 0:
            logger.info("rate limit: waiting %.1fs", remaining)
            time.sleep(remaining)

    def get_bytes(self, url: str, *, cache: bool | None = None) -> bytes:
        key = canonical_url(url)
        use_cache = self._use_cache(url, cache)
        if use_cache:
            cached = self._read_cache(key, url)
            if cached is not None:
                return cached
        self._wait_for_slot()
        logger.info("http GET %s", url)
        try:
            response = self._client.get(url)
            response.raise_for_status()
            data = response.content
        finally:
            self._last_live_request_at = time.monotonic()
        if use_cache:
            self._write_cache(key, data)
        return data

    def get_text(self, url: str, *, cache: bool | None = None) -> str:
        return decode_html_bytes(self.get_bytes(url, cache=cache))

    def post_form(
        self,
        url: str,
        data: dict[str, str],
        extra_headers: dict[str, str] | None = None,
        *,
        encoding: str = "utf-8",
        cache: bool = True,
        accept: str | None = None,
    ) -> str:
        body = urlencode(sorted(data.items()), encoding=encoding)
        key = f"POST {canonical_url(url)} {body}"
        use_cache = cache and self._use_cache(url, True)
        if use_cache:
            cached = self._read_cache(key, url)
            if cached is not None:
                return decode_html_bytes(cached)
        self._wait_for_slot()
        logger.info("http POST %s", url)
        headers = {
            "Accept": accept or ("application/json" if encoding == "utf-8" else "text/html"),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        if extra_headers:
            headers.update(extra_headers)
        try:
            response = self._client.post(url, content=body.encode("ascii"), headers=headers)
            response.raise_for_status()
            payload = response.content
        finally:
            self._last_live_request_at = time.monotonic()
        if use_cache:
            self._write_cache(key, payload)
        return decode_html_bytes(payload)


def join_url(base: str, path: str) -> str:
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))
