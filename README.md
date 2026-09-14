# local-council-system

地方議会の会議録を収集し、横断検索できる HTTP API として配布するシステムです。

国立国会図書館「国会会議録検索システム検索用API」に近い操作感を保ちつつ、自治体・都道府県・会期など地方議会固有の条件で検索できるようにします。

いま実装されている範囲は [実装状況](_docs/status.md) を正とします。Python 3.13 以上を想定しています。

## 2リポジトリ構成

| リポジトリ | 役割 |
| --- | --- |
| **local-council-data** | Canonical JSON の正本。自治体マスタ、JSON Schema、変更履歴を Git で管理する |
| **local-council-system**（本リポジトリ） | 収集・変換・検証、SQLite 生成、API 提供 |

データの正本は Git 上の Canonical JSON です。SQLite と API レスポンスは、正本から再生成できる派生データです。

## データフロー

3つのプロセスは独立しており、収集結果を検索用 SQLite へ直接書き込みません。

```text
地方議会Webサイト
        ↓
Collector Job          収集・正規化・検証 → data リポジトリへ PR
        ↓
Canonical JSON (Git)
        ↓
Database Builder Job   SQLite を全再構築
        ↓
API Server (FastAPI)   読み取り専用の検索 API
        ↓
利用者
```

## API

ベースパスは `/api`、応答は JSON、検索は HTTP GET です。

| エンドポイント | 内容 |
| --- | --- |
| `GET /api/meeting_list` | 会議のメタデータ（発言本文なし） |
| `GET /api/meeting` | 会議と、その会議の全発言 |
| `GET /api/speech` | 条件に一致した発言のみ |

```http
GET /api/speech?any=学校給食&municipalityCode=341002
```

パラメータ、レスポンス、ページングは [検索 API 仕様](_docs/api.md) を参照してください。

## 仕様の読み方

詳細は [`_docs/`](_docs/) にあります。README の次は、次の順で読む想定です。

| 順 | 文書 | この文書が定義すること |
| --- | --- | --- |
| — | [実装状況](_docs/status.md) | いま実装されている範囲、未実装、採用しないもの |
| 1 | [アーキテクチャ](_docs/architecture.md) | リポジトリ境界、3プロセス、CI、デプロイ |
| 2 | [データモデル](_docs/data.md) | Canonical JSON / Git / SQLite / API の対応 |
| 3 | [公開 ID](_docs/id.md) | Meeting / Speech の決定論的 UUIDv5 |
| 4 | [収集・同期](_docs/ingest-sync.md) | 初回同期、増分同期、lookback |
| 5 | [収集元](_docs/sources.md) | 自治体ごとの公開形態、実装タイプ、収集可否 |
| 6 | [CLI](_docs/cli.md) | サブコマンド、引数、終了コード |
| 7 | [検索 API](_docs/api.md) | パラメータ、レスポンス、ページング |

文書間で記述が重なる場合の優先関係は [`_docs/README.md`](_docs/README.md) を参照してください。
