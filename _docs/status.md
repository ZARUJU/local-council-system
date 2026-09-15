# 実装状況

この文書は、仕様のうち「いま実装されている範囲」と「まだやらない範囲」を一括して定義する。各領域の契約そのものは次を正とする。

- プロセス境界 → [architecture.md](architecture.md)
- Canonical / SQLite → [data.md](data.md)
- 公開 ID → [id.md](id.md)
- 収集・同期 → [ingest-sync.md](ingest-sync.md)
- 収集元の公開形態と可否 → [sources.md](sources.md)
- CLI の引数と終了コード → [cli.md](cli.md)
- 日々の起動と失敗時の対処 → [operation.md](operation.md)
- HTTP API の契約 → `local-council-api` の api.md

他文書は現状の進捗を書かない。実装の有無、収集対象の広さ、採用しない機能は本文書だけを更新する。

## 目次

- [いま通る経路](#いま通る経路)
- [プロセス](#プロセス)
- [収集対象](#収集対象)
- [CLI](#cli)
- [データと検索](#データと検索)
- [API](#api)
- [同期](#同期)
- [採用しないもの](#採用しないもの)
- [前提として固定していること](#前提として固定していること)

## いま通る経路

```text
広島市の公開 HTML、神戸市・広島県議会・廿日市市の dbsr HTML、
Discuss の閲覧 JSON、kensakusystem の閲覧 CGI
        ↓
collect
        ↓
Canonical JSON（schema / master / data）
        ↓
build-db
        ↓
検索用 SQLite
        ↓
local-council-api serve
        ↓
GET /api/speech
GET /api/meeting
GET /api/meeting_list
```

Collector は Canonical JSON までを書く。data リポジトリへの commit / Pull Request は行わない。API Server は本リポジトリに含めない。

## プロセス

| プロセス | CLI | 状態 |
| --- | --- | --- |
| Collector Job | `collect` | 実装済み |
| Database Builder Job | `build-db` | 実装済み。Canonical JSON から SQLite を全再構築する |
| API Server | `local-council-api serve` | `local-council-api` に実装済み。FastAPI。読み取り専用 |

## 収集対象

公開形態と収集してよいかは [sources.md](sources.md) を正とする。実装の有無は次とする。

| コード | 自治体 | adapter | 状態 | いまの範囲 |
| --- | --- | --- | --- | --- |
| `281000` | 神戸市 | `kobe-dbsr` | 実装済み | 2025 年以降。本会議の本文のみ。名簿・資料は対象外。検索一覧は GET `Page` で全ページを辿る。委員会は後続 |
| `340006` | 広島県 | `dbsr` | 実装済み | 2025 年以降。本会議の本文のみ。定例会と臨時会。名簿・資料は対象外。委員会は後続 |
| `341002` | 広島市 | `hiroshima-voices` | 実装済み | 2025 年以降。本会議と、委員会閲覧画面の個別委員会。「すべて表示」は対象外 |
| `342025` | 呉市 | `discuss` | 実装済み | 2025 年以降。本会議の日程・号のみ。委員会・資料・名簿は対象外 |
| `342041` | 三原市 | `discuss` | 実装済み | 同上 |
| `342050` | 尾道市 | `discuss` | 実装済み | 同上 |
| `342076` | 福山市 | `discuss` | 実装済み | 同上 |
| `342106` | 庄原市 | `discuss` | 実装済み | 同上 |
| `342122` | 東広島市 | `discuss` | 実装済み | 同上 |
| `345458` | 神石高原町 | `discuss` | 実装済み | 同上 |
| `342084` | 府中市 | `kensakusystem` | 実装済み | 2025 年以降。本会議の定例会・臨時会のみ。委員会は対象外 |
| `342114` | 大竹市 | `kensakusystem` | 実装済み | 同上 |
| `342131` | 廿日市市 | `dbsr` | 実装済み | 2025 年以降。本会議の本文のみ。定例会と臨時会。名簿・資料は対象外。委員会は後続 |
| `342149` | 安芸高田市 | `kensakusystem` | 実装済み | 2025 年以降。本会議の定例会・臨時会のみ。委員会は対象外 |
| `382019` | 松山市 | `discuss` | 実装済み | 2025 年以降。本会議の日程・号のみ。委員会・資料・名簿は対象外 |

設定 yaml は実装済みの自治体だけ `config/sources/` に置く。見送りの自治体を yaml だけ置いて CLI から呼べる状態にしてはならない。

dbsr は `listingPath` / `queryType` / `cabinets` で差を yaml に置く。Discuss は `tenantId` / `tenantSlug` で差を yaml に置く。kensakusystem は `baseUrl` の slug で差を yaml に置く。

## CLI

実装済み:

```text
local-council-system collect --municipality <code>
local-council-system build-db
```

`collect` の試行オプション `--since` `--until` `--limit` `--source-meeting-id` `--discover-only` `--no-cache` は実装済みである。別名 `--fino` も受け付ける。新規の説明では `--source-meeting-id` を使う。

未実装:

```text
local-council-system collect --all
local-council-system collect --all --adapter hiroshima-voices
```

`--all` と `--adapter` は [cli.md](cli.md) に契約がある。実装するまでの間、`--municipality` が必須である。

`build-db` は常に全再構築する。`--full` は受け付けるが、省略しても同じである。差分更新は未実装である。

CLI に含めない:

- 対話モード
- 進捗バー
- 並列実行オプション
- 自治体を超えたグローバルな `--jobs`
- サブコマンド内での Git commit / `gh pr create`
- `collect` から検索用 SQLite を直接更新するフラグ
- `serve`（API は `local-council-api`）
- パスワードや API キーを引数で受け取るオプション
- 機械可読なサマリ JSON の標準出力

## データと検索

実装済み:

- Canonical JSON（1 会議 1 ファイル）と JSON Schema 検証
- 自治体マスタ `master/municipalities.json`
- 検索用 SQLite の `municipalities` / `meetings` / `speeches`
- 発言本文検索は SQLite `LIKE`

正本へ保存しない:

- HTML や PDF のバイト列

作らない:

- Speaker 専用テーブル
- 全文検索エンジン / FTS5
- SQLite の差分更新
- Canonical の `identityVersion` フィールド

## API

HTTP API の実装と契約の正は `local-council-api` である。本リポジトリは検索用 SQLite を生成して渡す。

## 同期

実装済み:

```text
Collection State = lastSuccessfulSync
保管先: {dataRoot}/status/{municipalityCode}.json（data リポジトリ。会議の正本ではない）
初回: collection.initialFrom
増分: lastSuccessfulSync - lookbackDays
既定 lookback: 30 日
結果: success / failed
```

同期結果に `partial` は無い。Lookback 対象は原則として再取得・再解析する。ETag や Last-Modified によるスキップはしない。

必須としない:

- 会議単位の再開カーソル
- ページ単位の再開位置
- `lastAttemptedSync` / `lastFailedSync`
- 前回取得 URL
- 会議ごとの取得状態永続化
- 複雑な Retry Queue
- Collection State 専用の履歴テーブル（Git 履歴で足りる）

## 採用しないもの

次は仕様の将来拡張として残してよいが、いまは実装しない。

- PDF / OCR
- OpenSearch および高度な全文検索
- 差分 SQLite 更新
- 分散 Queue / 複数 Worker
- 複雑な Retry 管理
- 管理画面
- Collector の自動 commit / PR
- データ更新用 HTTP API

デプロイの第一候補は GitHub を使う構成である。具体的なホスティングは固定しない。

## 前提として固定していること

進捗ではなく、現行仕様として他文書と共有する前提である。

```text
リポジトリ:     local-council-system、local-council-data、local-council-api
データ正本:     Git 上の Canonical JSON
派生:           SQLite と API
データ更新:     Pull Request。通常更新は CI 成功時の自動マージを許容
プロセス:       Collector / Database Builder / API Server の 3 分離
検索 DB:        Canonical JSON から全再構築
作業用 DB:      Collector 内の SQLite を許可する。正本および API 入力ではない
公開 ID:        決定論的な UUIDv5。ランダム ID は使わない
API:            FastAPI、読み取り専用、HTTP GET、JSON
CLI:            単発。スケジューラは外部
終了コード:     0 成功 / 1 処理失敗 / 2 使い方・設定誤り
Python:         3.13 以上
```
