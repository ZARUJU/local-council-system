# CLI

この文書は、local-council-system のコマンドラインインタフェースを定義します。収集範囲と同期成否は [ingest-sync.md](ingest-sync.md)、対象自治体と実装タイプは [sources.md](sources.md)、プロセス分離は [architecture.md](architecture.md) を参照してください。いま実装されているコマンドとオプションは [status.md](status.md) を正とします。HTTP API の起動は `local-council-api` の cli.md を正とします。

関連:

- 実装状況 → [status.md](status.md)
- Collector / Database Builder の責務 → [architecture.md](architecture.md)
- 初回同期・増分同期・lookback → [ingest-sync.md](ingest-sync.md)
- 自治体ごとの公開形態と収集可否 → [sources.md](sources.md)
- Canonical JSON の出力形 → [data.md](data.md)
- 日々の起動と失敗時の対処 → [operation.md](operation.md)
- API Server の起動 → `local-council-api` の cli.md
- 文書の読み順と優先関係 → [README.md](README.md)

## 目次

- [目的](#目的)
- [起動方法](#起動方法)
- [設計方針](#設計方針)
- [コマンド一覧](#コマンド一覧)
- [共通規則](#共通規則)
- [collect](#collect)
- [build-db](#build-db)
- [終了コード](#終了コード)
- [標準出力・ログ](#標準出力ログ)
- [設定ファイルと作業ディレクトリ](#設定ファイルと作業ディレクトリ)

## 目的

収集・生成の 2 プロセスを、外部スケジューラから起動できる CLI として提供する。

```text
collect   Collector Job
build-db  Database Builder Job
```

API Server は `local-council-api` が起動する。スケジュール機能そのものはアプリケーションへ組み込まない。cron、systemd timer、GitHub Actions 等が本 CLI を呼ぶ。

## 起動方法

プログラム名は `local-council-system` とする。次のどれで起動してもよい。意味は同一である。

```bash
local-council-system <command> [options]
python -m local_council_system <command> [options]
uv run local-council-system <command> [options]
```

作業ディレクトリは、リポジトリ `local-council-system` のルートを前提とする。相対パス（`config/`、`var/`）はカレントディレクトリから解決する。

## 設計方針

### サブコマンドでプロセスを分ける

フラグの組合せで Collector と DB 構築を切り替えない。1 サブコマンドが 1 プロセスに対応する。

### 対象の絞り込みは明示する

本番の定期実行は、設定ファイルと Collection State に従う。試行・負荷抑制のための絞り込みは CLI オプションで明示し、その実行では同期成功とみなして `lastSuccessfulSync` を更新しない。

### Adapter 固有の識別子を汎用 CLI の必須引数にしない

自治体の指定は全国地方公共団体コードとする。収集元固有 ID（例: VOICES の `FINO`）は、試行用の任意オプションに限る。

### 破壊的操作を隠さない

Canonical JSON の上書き、SQLite の全再構築、HTTP キャッシュの無効化は、オプション名から意図が分かるようにする。

## コマンド一覧

| コマンド | プロセス | 役割 |
| --- | --- | --- |
| `collect` | Collector Job | DISCOVER から EXPORT まで |
| `build-db` | Database Builder Job | Canonical JSON から検索用 SQLite を全再構築 |

`serve` は本 CLI に含めない。API の起動は `local-council-api serve` である。実装の有無は [status.md](status.md) を正とする。

ヘルプ:

```bash
local-council-system -h
local-council-system collect -h
```

## 共通規則

### 日付

日付オプションの形式は `YYYY-MM-DD` とする。タイムゾーンを付けない。開催日として解釈する。

不正な形式は終了コード 2 で終了する。

### 真偽フラグ

デフォルトオフの動作を有効にする場合は `--discover-only` のように affirmative な長いオプションを使う。デフォルトオンの動作を切る場合は `--no-cache` のように否定形を使う。

### 対象自治体

`config/sources/{municipalityCode}.yaml` が存在しないコードを指定した場合は終了コード 2 とする。

## collect

対象自治体の公開会議録を発見、取得、解析、検証し、Canonical JSON を出力する。

```text
local-council-system collect --municipality <code> [options]
```

処理段階は次とする。詳細は [architecture.md](architecture.md) と [ingest-sync.md](ingest-sync.md) を正とする。

```text
DISCOVER → FETCH → PARSE → NORMALIZE → VALIDATE → EXPORT
```

### 対象の指定

次のいずれかが必須である。両方を同時に指定してはならない。

| オプション | 内容 |
| --- | --- |
| `--municipality <code>` | 全国地方公共団体コード 1 件。例: `341002` |
| `--all` | `config/sources/` にある全自治体 |

`--all` と `--adapter` の実装状況は [status.md](status.md) を正とする。未実装の間は `--municipality` を必須とする。

将来、収集元製品で絞る場合は次を追加してよい。

| オプション | 内容 |
| --- | --- |
| `--adapter <name>` | 設定の `adapter` が一致する自治体だけを対象にする |

`--adapter` 単体では `--municipality` / `--all` の代わりにならない。`--all --adapter hiroshima-voices` のように組み合わせる。

`adapter` 値は [sources.md](sources.md) の対象自治体表を正とする。

### 探索範囲

探索開始点 `since` の既定値は、CLI ではなく Collector Service が [ingest-sync.md](ingest-sync.md) に従って決める。

```text
lastSuccessfulSync なし → 設定の initialFrom
lastSuccessfulSync あり → lastSuccessfulSync - lookbackDays
```

CLI で上書きできる範囲は次とする。

| オプション | 型 | 既定 | 内容 |
| --- | --- | --- | --- |
| `--since <date>` | `YYYY-MM-DD` | なし | 開催日の下限。指定時は Collection State より優先する |
| `--until <date>` | `YYYY-MM-DD` | なし | 開催日の上限。省略時は Adapter が取得可能な最新まで |

上下限は開催日に対して閉区間とする。`--since 2025-09-17 --until 2025-09-17` はその日の会議のみを対象にする。

### 試行・負荷抑制

公開サイトへ与える負荷を抑えるため、次を指定できる。

| オプション | 型 | 既定 | 内容 |
| --- | --- | --- | --- |
| `--limit <n>` | 0 以上の整数 | なし | DISCOVER 後、処理する会議数の上限 |
| `--source-meeting-id <id>` | 文字列 | なし | 収集元の会議 ID が一致するものだけを処理する |
| `--discover-only` | フラグ | オフ | 一覧の発見だけ行い、本文取得以降を行わない |
| `--no-cache` | フラグ | オフ | HTTP ディスクキャッシュを使わず、毎回 origin へアクセスする |

`--source-meeting-id` の広島市 VOICES における値は `FINO` である。別名 `--fino` も受け付ける。新規の説明では `--source-meeting-id` を使う。

`--limit` は DISCOVER 結果を日付・号・収集元 ID の昇順で並べた先頭 n 件に適用する。

`--discover-only` のとき FETCH 以降を実行しない。公開サイトへのアクセスは、年別一覧など DISCOVER に必要なリクエストに限る。

### 出力先

| オプション | 既定 | 内容 |
| --- | --- | --- |
| `--data-root <path>` | 設定の `export.dataRoot`（広島市は `../local-council-data`） | Canonical JSON と収集カーソルのルート |

ファイル配置は [data.md](data.md) に従う。

```text
{dataRoot}/
├── schema/
│   ├── meeting.schema.json
│   ├── municipalities.schema.json
│   └── collection-status.schema.json
├── master/
│   └── municipalities.json
├── data/{都道府県コード}/{municipalityCode}/{年}/{YYYY-MM-DD-NNN}.json
└── status/{municipalityCode}.json
```

例:

```text
../local-council-data/data/34/341002/2025/2025-09-17-001.json
../local-council-data/master/municipalities.json
../local-council-data/status/341002.json
```

内容に変更がなければファイルを書き換えない。

本コマンドの出力は Canonical JSON までとする。data リポジトリへの commit / Pull Request は対象外である。Git 操作は Collector Job の外側、または後続の専用コマンドとして追加する。

### HTTP とキャッシュ

HTTP の間隔、タイムアウト、User-Agent、キャッシュの既定は各自治体設定の `http` 節が持つ。CLI はキャッシュの可否だけを `--no-cache` で上書きする。

キャッシュを使う場合の保存先は次とする。

```text
var/http-cache/
```

キャッシュヒット時は origin へアクセスせず、レート制限の待ちも入れない。Lookback 時の再取得を強制するには `--no-cache` を付ける。

### Collection State の更新

保存先は [ingest-sync.md](ingest-sync.md) どおり次とする。

```text
{dataRoot}/status/{municipalityCode}.json
```

次のすべてを満たすときだけ `lastSuccessfulSync` を更新する。

- 今回の対象会議が 1 件以上ある
- 対象会議の FETCH 以降がすべて成功した
- `--discover-only` ではない
- `--since`、`--until`、`--limit`、`--source-meeting-id`（`--fino`）のいずれも指定していない
- `--all` 実行時は、対象にした全市区町村が上記を満たす

試行オプションを付けた実行は、成功しても同期成功として記録しない。次回の本番実行が初回同期または前回成功時点からの lookback を維持するためである。

`--until` だけを付けた場合も試行とみなす。本番の増分同期は開催日上限を切らない。

### 呼び出し例

広島市議会（本会議、2025年以降）を試す。

```bash
# 一覧だけ見る。本文は取らない
local-council-system collect --municipality 341002 --until 2025-12-31 --discover-only

# 1 会議だけ本文まで通す（広島市 VOICES の FINO。本会議）
local-council-system collect --municipality 341002 --source-meeting-id 5145 --until 2025-12-31

# 2025年の本会議・委員会を data リポジトリへ書く
local-council-system collect --municipality 341002 --since 2025-01-01 --until 2025-12-31

# 期間を区切って最大 3 件
local-council-system collect --municipality 341002 --since 2025-09-01 --until 2025-09-30 --limit 3

# 神戸市会（dbsr）。本文のみ。名簿・資料は取らない
local-council-system collect --municipality 281000 --since 2025-03-01 --until 2025-03-31 --limit 1
```

本番相当（設定の `initialFrom` / lookback に従い、成功時に State を更新する）:

```bash
local-council-system collect --municipality 341002
```

広島市の初期設定では 2025年以降の本会議が対象である。件数が多いため、Adapter が安定するまでは `--limit` 付きの試行を先に使う。

`--all` の呼び出しは [status.md](status.md) を正とする。

## build-db

Canonical JSON から検索用 SQLite を全再構築する。

```text
local-council-system build-db [options]
```

| オプション | 内容 |
| --- | --- |
| `--data-root <path>` | 入力とする Canonical JSON のルート。既定は `../local-council-data` |
| `--output <path>` | 生成する SQLite ファイル。既定は `var/search.sqlite` |
| `--full` | 全再構築。省略しても全再構築する |

入力は Collector の作業用 SQLite ではない。Git 上の Canonical JSON、またはそれに相当する `data-root` である。

生成は一時ファイルへ行い、成功後に本番ファイルへ置換する。詳細は [architecture.md](architecture.md) を正とする。配布側が読むパスは、運用で `local-council-api serve --database` に渡す。

## 終了コード

| コード | 意味 |
| --- | --- |
| 0 | 指定した対象を処理し、失敗が 0 件 |
| 1 | 対象の処理中に 1 件以上失敗した |
| 2 | 使い方の誤り、未知コマンド、設定欠落、未対応 Adapter |

`--discover-only` が正常終了したときは 0 を返す。一覧が 0 件でも、DISCOVER 自体が成功していれば 0 とする。

`collect --all` では、1 自治体でも失敗すれば全体を 1 とする。

## 標準出力・ログ

ログは標準エラーへ出す。形式は次を基本とする。

```text
{ISO8601} {LEVEL} {message}
```

Collector が最低限記録するもの:

```text
municipalityCode
discover した会議数
success count
failure count
written count（内容変更のあった JSON 数）
sync=success|failed
```

個人情報に該当し得る発言本文を、ログレベル INFO で出してはならない。失敗時の traceback は標準エラーへ出してよい。

`--discover-only` では、発見した会議の収集元 ID、開催日、題名ヒントを INFO で出してよい。

機械可読なサマリ JSON を標準出力へ出すことは必須としない。

## 設定ファイルと作業ディレクトリ

### 自治体設定

```text
config/sources/{municipalityCode}.yaml
```

CLI が読む最低限の項目:

```yaml
municipalityCode: "341002"
adapter: "hiroshima-voices"

source:
  system: "voices"
  baseUrl: "https://hiroshima.gijiroku.com"
  minutesBaseUrl: "https://hiroshima.gijiroku.com/voices"

collection:
  initialFrom: "2025-01-01"
  lookbackDays: 30
  earliestYear: 2025

http:
  minIntervalSeconds: 3
  timeoutSeconds: 30
  cache: true

export:
  dataRoot: "../local-council-data"
```

`collection.*` の意味は [ingest-sync.md](ingest-sync.md) を正とする。`earliestYear` は Adapter が DISCOVER で遡る西暦年の下限である。神戸市は `281000.yaml` を同じ項目で持つ。

### Git 管理外の作業領域

```text
var/
├── http-cache/
├── canonical/
└── search.sqlite
```

`var/` は `.gitignore` で除外する。正本ではない。収集カーソルはここへ置かない。

| パス | 役割 | 消してよいか |
| --- | --- | --- |
| `{dataRoot}/status/{code}.json` | 自治体ごとの `lastSuccessfulSync` | 消すと次回が初回同期になる。data リポジトリの Git で残す |
| `var/http-cache/` | 開発・再実行用の HTTP キャッシュ | 消してよい。次の実行が origin へアクセスする |
| `var/canonical/` | 開発時の JSON 出力（旧既定） | 消してよい。正本は `../local-council-data` |
| `var/search.sqlite` | 検索用 SQLite（`build-db` の既定出力） | 消してよい。Canonical JSON から再生成する |

対話モード、進捗バー、並列実行、認証情報を引数で受け取るオプションなど、CLI に含めない事項は [status.md](status.md) を正とする。
