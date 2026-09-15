# local-council-system

地方議会の会議録を収集し、検索用 SQLite まで生成するシステムです。HTTP API による配布は sibling の `local-council-api` が担います。

いま実装されている範囲は [実装状況](_docs/status.md) を正とします。Python 3.13 以上を想定しています。

## 3リポジトリ構成

| リポジトリ | 役割 |
| --- | --- |
| **local-council-data** | Canonical JSON の正本。自治体マスタ、JSON Schema、変更履歴を Git で管理する |
| **local-council-system**（本リポジトリ） | 収集・変換・検証、検索用 SQLite の生成 |
| **local-council-api** | 検索用 SQLite を読み、HTTP API として配布する |

データの正本は Git 上の Canonical JSON です。SQLite と API レスポンスは、正本から再生成できる派生データです。

## データフロー

収集・生成と配布は独立しており、収集結果を検索用 SQLite へ直接書き込みません。

```text
地方議会Webサイト
        ↓
Collector Job          収集・正規化・検証 → Canonical JSON
        ↓
Canonical JSON (Git)
        ↓
Database Builder Job   SQLite を全再構築
        ↓
検索用 SQLite
        ↓
local-council-api      読み取り専用の検索 API
        ↓
利用者
```

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
| 7 | [運用](_docs/operation.md) | 日々の起動、定期実行、失敗時の対処 |

HTTP API のパラメータ、レスポンス、ページングは `local-council-api` の [検索 API 仕様](../local-council-api/_docs/api.md) を正とします。

文書間で記述が重なる場合の優先関係は [`_docs/README.md`](_docs/README.md) を参照してください。
