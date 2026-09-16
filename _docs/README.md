# 仕様書

本ディレクトリは local-council-system の実装固有仕様を定義します。収集・生成の範囲を扱います。リポジトリ境界、Canonical Data、公開 ID、実装状況の俯瞰は sibling の `local-council-docs` が正です。HTTP API の契約は sibling の `local-council-api` が正です。

最初にリポジトリ直下の [README.md](../README.md) を読み、横断仕様は `local-council-docs` へ進んでください。いま動く範囲は `local-council-docs` の status.md だけを正とします。

## 文書一覧

横断:

| 文書 | 定義すること |
| --- | --- |
| `local-council-docs` の [status.md](../../local-council-docs/status.md) | いま実装されている範囲、未実装、採用しないもの |
| `local-council-docs` の [architecture.md](../../local-council-docs/architecture.md) | システム境界、プロセス分離、CI、デプロイ |
| `local-council-docs` の [data.md](../../local-council-docs/data.md) | Canonical / Git / SQLite / API の対応 |
| `local-council-docs` の [id.md](../../local-council-docs/id.md) | Meeting / Speech の公開 ID |

本リポジトリ:

| 文書 | 定義すること | 読者 |
| --- | --- | --- |
| [ingest-sync.md](ingest-sync.md) | Collection State、初回同期、増分同期、lookback | Collector を実装・運用するとき |
| [sources.md](sources.md) | 自治体ごとの公開形態、実装タイプ、収集可否 | Adapter を追加・見送るとき |
| [cli.md](cli.md) | CLI のコマンド体系、起動方法、終了コード | ジョブを起動・試行するとき |
| [operation.md](operation.md) | 日々の起動、定期実行、成果物の受け渡し、失敗時の対処 | 収集・生成を運用するとき |
| [api.md](api.md) | HTTP API の契約は `local-council-api` を正とする。本リポジトリはポインタ | API 契約の所在を知りたいとき |
| [architecture.md](architecture.md) / [data.md](data.md) / [id.md](id.md) / [status.md](status.md) | 上記横断文書へのポインタ | 旧パスからの案内 |

## 推奨する読み順

```text
local-council-docs の README.md
    ↓
status.md / architecture.md / data.md / id.md
    ↓
ingest-sync.md
    ↓
sources.md
    ↓
cli.md
    ↓
operation.md
```

## 文書間で重なる記述の優先

同じ事柄を複数の文書が触れる場合、次を正とします。

| 事柄 | 正とする文書 |
| --- | --- |
| いま実装されている範囲、未実装、採用しない機能 | `local-council-docs` の status.md |
| プロセス分離、CI、デプロイ、障害分離 | `local-council-docs` の architecture.md |
| Canonical フィールド、Git 配置、SQLite スキーマ、層間マッピング | `local-council-docs` の data.md |
| 公開 ID の生成・維持・禁止事項 | `local-council-docs` の id.md |
| 収集範囲、`lastSuccessfulSync`、lookback、同期の成否 | [ingest-sync.md](ingest-sync.md) |
| 対象自治体、実装タイプ、収集してよい原資料 | [sources.md](sources.md) |
| CLI のサブコマンド、引数、終了コード、起動方法 | [cli.md](cli.md) |
| 日々の起動、定期実行、成果物の受け渡し、失敗時の対処 | [operation.md](operation.md) |
| リクエスト、レスポンス、ページング、HTTP エラー | `local-council-api` の api.md |
