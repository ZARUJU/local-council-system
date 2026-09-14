from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from local_council_system.adapters.registry import create_adapter
from local_council_system.api.app import create_app
from local_council_system.collectors.service import CollectOptions, CollectorService
from local_council_system.config import load_municipality_config
from local_council_system.db.builder import build_search_database
from local_council_system.http_client import PoliteHttpClient
from local_council_system.validators.meeting import ValidationError

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="local-council-system",
        description="地方議会会議録の収集・変換",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="自治体の会議録を収集する")
    collect.add_argument("--municipality", required=True, help="全国地方公共団体コード")
    collect.add_argument("--limit", type=int, default=None, help="処理する会議数の上限（負荷抑制用）")
    collect.add_argument("--since", default=None, help="YYYY-MM-DD 以降（開催日）。試行時の範囲絞り込み用")
    collect.add_argument(
        "--source-meeting-id",
        "--fino",
        dest="source_meeting_id",
        default=None,
        help="収集元の会議 ID（広島市は FINO、神戸市は Id）",
    )
    collect.add_argument("--until", default=None, help="YYYY-MM-DD まで（開催日）。試行時の範囲絞り込み用")
    collect.add_argument("--discover-only", action="store_true", help="一覧だけ取得して本文は取らない")
    collect.add_argument("--no-cache", action="store_true", help="HTTPキャッシュを使わない")
    collect.add_argument(
        "--data-root",
        default=None,
        help="Canonical JSON の出力先（省略時は設定ファイル）",
    )
    build = sub.add_parser("build-db", help="Canonical JSON から検索用 SQLite を全再構築する")
    build.add_argument(
        "--data-root",
        default="../local-council-data",
        help="入力とする Canonical JSON のルート",
    )
    build.add_argument(
        "--output",
        default="var/search.sqlite",
        help="生成する SQLite ファイル",
    )
    build.add_argument("--full", action="store_true", help="全再構築（省略しても全再構築する）")
    serve = sub.add_parser("serve", help="検索 API を起動する")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--database",
        default="var/search.sqlite",
        help="検索用 SQLite のパス",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    if args.command == "collect":
        return _collect(args)
    if args.command == "build-db":
        return _build_db(args)
    if args.command == "serve":
        return _serve(args)
    parser.error(f"unknown command: {args.command}")
    return 2


def _collect(args: argparse.Namespace) -> int:
    config = load_municipality_config(args.municipality)
    cache_dir = Path("var/http-cache") if (config.http.cache and not args.no_cache) else None
    http = PoliteHttpClient(
        user_agent=config.http.user_agent,
        min_interval_seconds=config.http.min_interval_seconds,
        timeout_seconds=config.http.timeout_seconds,
        cache_dir=cache_dir,
        cache_enabled=cache_dir is not None,
    )
    try:
        adapter = create_adapter(config, http)
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    data_root = Path(args.data_root) if args.data_root else config.export_root
    service = CollectorService(
        config=config,
        adapter=adapter,
        data_root=data_root,
    )
    until = date.fromisoformat(args.until) if args.until else None
    since = date.fromisoformat(args.since) if args.since else None
    trial = any(
        [
            args.limit is not None,
            args.source_meeting_id is not None,
            since is not None,
            until is not None,
            args.discover_only,
        ]
    )
    result = service.run(
        CollectOptions(
            limit=args.limit,
            since=since,
            until=until,
            fino=args.source_meeting_id,
            discover_only=args.discover_only,
            update_state=not trial,
        )
    )
    logger.info(
        "collect done discovered=%s succeeded=%s failed=%s written=%s sync=%s",
        result.discovered,
        result.succeeded,
        result.failed,
        result.written,
        "success" if result.sync_success else "failed",
    )
    return 0 if result.failed == 0 else 1


def _build_db(args: argparse.Namespace) -> int:
    data_root = Path(args.data_root)
    output = Path(args.output)
    if not data_root.exists():
        logger.error("data root not found: %s", data_root)
        return 2
    try:
        result = build_search_database(data_root, output)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 2
    except ValidationError as exc:
        logger.error("build-db validation failed: %s", exc)
        return 1
    logger.info(
        "build-db done municipalities=%s meetings=%s speeches=%s output=%s",
        result.municipalities,
        result.meetings,
        result.speeches,
        result.output,
    )
    return 0


def _serve(args: argparse.Namespace) -> int:
    database = Path(args.database)
    if not database.exists():
        logger.error("search database not found: %s", database)
        return 2
    import uvicorn

    app = create_app(database)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
