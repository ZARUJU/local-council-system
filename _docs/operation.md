# 運用

この文書は、local-council-system の日々の起動、定期実行、成果物の受け渡し、失敗時の対処を定義します。コマンドの引数と終了コードは [cli.md](cli.md)、同期の成否は [ingest-sync.md](ingest-sync.md)、プロセス境界は [architecture.md](../../local-council-docs/architecture.md) を正とします。いま実装されている範囲は [status.md](../../local-council-docs/status.md) を正とします。

関連:

- 実装状況 → [status.md](../../local-council-docs/status.md)
- プロセス分離、障害分離 → [architecture.md](../../local-council-docs/architecture.md)
- 初回同期・増分同期・lookback → [ingest-sync.md](ingest-sync.md)
- 対象自治体 → [sources.md](sources.md)
- CLI の引数と終了コード → [cli.md](cli.md)
- 配布側の起動 → `local-council-api` の operation.md
- 文書の読み順と優先関係 → [README.md](README.md)

## 目次

- [目的](#目的)
- [前提](#前提)
- [日常の流れ](#日常の流れ)
- [collect](#collect)
- [build-db](#build-db)
- [成果物の受け渡し](#成果物の受け渡し)
- [定期実行](#定期実行)
- [失敗したとき](#失敗したとき)
- [消してよいもの](#消してよいもの)
- [やってはいけないこと](#やってはいけないこと)
- [ログ](#ログ)

## 目的

収集と検索用 SQLite 生成を、外部スケジューラまたは手元から回す手順を固定する。本リポジトリは API Server を起動しない。

## 前提

作業ディレクトリは `local-council-system` のルートとする。Python 3.13 以上。相対パスはカレントディレクトリから解決する。

```text
local-council-data/          Canonical JSON の正本。既定の --data-root
local-council-system/        本リポジトリ
local-council-api/           配布。本リポジトリはここへ SQLite を渡すだけ
```

`config/sources/{municipalityCode}.yaml` がある自治体だけを対象にする。実装済みの一覧は [status.md](../../local-council-docs/status.md) を正とする。

## 日常の流れ

```text
1. collect（自治体ごと）
2. Canonical JSON の差分を確認する
3. local-council-data へ commit / Pull Request（本 CLI の外）
4. build-db
5. 生成した SQLite を local-council-api へ渡す
```

Collector は Canonical JSON までを書く。Git commit と Pull Request は本 CLI に含めない。実装状況は [status.md](../../local-council-docs/status.md) を正とする。

## collect

本番は設定の `initialFrom` / lookback に従う。試行オプションを付けない。

```bash
uv run local-council-system collect --municipality 341002
```

`--all` は未実装である。実装済みの自治体は 1 件ずつ起動する。対象コードは [status.md](../../local-council-docs/status.md) を正とする。

試行（期間・件数・会議 ID の絞り込み、`--discover-only`）は Adapter の確認と負荷抑制に使う。成功しても `lastSuccessfulSync` を更新しない。引数の意味は [cli.md](cli.md) を正とする。

```bash
uv run local-council-system collect --municipality 341002 --until 2025-12-31 --discover-only
uv run local-council-system collect --municipality 341002 --source-meeting-id 5145 --until 2025-12-31 --limit 1
```

HTTP 間隔は各 yaml の `http.minIntervalSeconds` に従う。キャッシュは `var/http-cache/`。Lookback で origin から取り直すときは `--no-cache` を付ける。

終了コード:

| コード | 運用上の意味 |
| --- | --- |
| 0 | 対象を処理し、失敗 0 件。差分があれば data リポジトリで確認する |
| 1 | 1 件以上失敗。`lastSuccessfulSync` は更新されていない前提で、ログを見て当該自治体を再実行する |
| 2 | 使い方・設定誤り。yaml 欠落、未対応 Adapter、日付形式など。直してから再実行する |

公開サイトへ負荷をかけない。失敗した自治体を短い間隔で連続再実行しない。

## build-db

`local-council-data` の Canonical JSON を入力とし、検索用 SQLite を全再構築する。Collector の作業用 SQLite は入力にしない。

```bash
uv run local-council-system build-db
uv run local-council-system build-db --data-root ../local-council-data --output var/search.sqlite
```

生成は一時ファイルへ行い、成功後に本番ファイルへ置換する。失敗した中間ファイルを API へ渡してはならない。方式は [architecture.md](../../local-council-docs/architecture.md) を正とする。

入力は、運用上は data リポジトリの main（またはそれに相当する checkout）とする。未マージの作業ツリーだけを本番 SQLite の入力にしてはならない。

終了コード 2 は data-root 欠落など。終了コード 1 は検証失敗。既存の `var/search.sqlite` は残る。API は既存ファイルを使い続けてよい。

## 成果物の受け渡し

本リポジトリの成果物は次の 2 つである。

| 成果物 | 置き場 | 渡す先 |
| --- | --- | --- |
| Canonical JSON と収集カーソル | `{dataRoot}`（既定 `../local-council-data`） | Git。会議の正本は JSON。カーソルは `status/` |
| 検索用 SQLite | 既定 `var/search.sqlite` | `local-council-api` |

SQLite は正本ではない。消して再生成してよい。API ホストへコピーまたは `--database` で渡す。受け側の起動と入れ替えは `local-council-api` の operation.md を正とする。

本プロセスは API Server の再起動を担わない。新しい SQLite の生成失敗は、既存 API を止めない。

## 定期実行

スケジュール機能はアプリケーションへ組み込まない。cron、systemd timer、GitHub Actions 等から本 CLI を呼ぶ。間隔の具体値は本仕様では固定しない。

推奨する順序:

```text
自治体ごとに collect
    ↓
失敗 0 件の差分だけ data へ載せる
    ↓
build-db
    ↓
SQLite を API へ渡す
```

collect と build-db を 1 プロセスにまとめない。collect が失敗しても、前回成功した Canonical JSON から SQLite を再生成できる。

収集カーソルは data リポジトリの `status/{municipalityCode}.json` にある。実行環境に `var/` を残す必要はない。`var/http-cache/` は次回 origin へアクセスすれば足りる。

## 失敗したとき

### collect が 1

ログの `failed` と traceback を見る。公開サイトの仕様変更、一時的な HTTP エラー、Parser 不具合を切り分ける。

- 一時的なら、間隔を空けて同じコマンドを再実行する
- サイト変更なら Adapter を直してから試行オプションで確認し、本番相当を再実行する
- 誤った JSON を書いた場合は data リポジトリの差分を捨てるか、修正後に再 collect する。検索用 SQLite を手で直さない

`lastSuccessfulSync` は成功時だけ更新される。失敗後の次回本番実行は、前回成功時点からの lookback を維持する。意味は [ingest-sync.md](ingest-sync.md) を正とする。

### collect が 2

対象コードの yaml が無い、Adapter 未対応、日付が `YYYY-MM-DD` でない、など。設定と引数を直す。公開サイトへはアクセスしていないことがある。

### 件数が急減した、発言が空になった

既存会議の発言数が急減した場合、または `speeches = []` になった場合は原則として異常とする。その差分を data の main へ載せない。CI Validation の方針は [architecture.md](../../local-council-docs/architecture.md) を正とする。

### build-db が失敗した

既存の `var/search.sqlite` を残す。API には渡さない。入力 JSON の Schema 違反や未知の `municipalityCode` を直してから再実行する。

### 収集カーソルを消した

`status/{code}.json` を消すと、次回はその自治体が初回同期になる。意図せず消した場合は data リポジトリの Git から戻す。会議 JSON からは復元しない。

## 消してよいもの

| パス | 消したあとの影響 |
| --- | --- |
| `var/http-cache/` | 次の collect が origin へアクセスする |
| `var/canonical/` | 正本ではない。正本は `../local-council-data` |
| `var/search.sqlite` | Canonical JSON から `build-db` で再生成する |

`{dataRoot}/status/{code}.json` は消すと初回同期に戻る。data リポジトリの Git で残す。

## やってはいけないこと

- 検索用 SQLite へ収集結果を直接書く
- `collect` から API 用 SQLite を更新する
- Collector 内で Git commit / `gh pr create` する（未実装であり、CLI に含めない）
- 失敗した build の一時ファイルを API へ渡す
- 取得した HTML をコードとして評価する
- GitHub Token をソースまたは Canonical JSON へ置く
- 発言本文を INFO ログへ出す

## ログ

ログは標準エラーへ出す。Collector と Database Builder が最低限出す項目は [architecture.md](../../local-council-docs/architecture.md) と [cli.md](cli.md) を正とする。

運用で見るもの:

```text
municipalityCode
discovered / succeeded / failed / written
sync=success|failed
build-db の municipalities / meetings / speeches
```

`written` が 0 でも終了コード 0 なら、差分なしとして正常である。
