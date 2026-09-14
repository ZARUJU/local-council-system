# アーキテクチャ

この文書は、収集から API 配布までのシステム境界、プロセス分離、CI、デプロイを定義します。

関連:

- 正本・派生データの形 → [data.md](data.md)
- 公開 ID → [id.md](id.md)
- 初回同期・増分同期 → [ingest-sync.md](ingest-sync.md)
- HTTP API の契約 → [api.md](api.md)
- 文書の読み順と優先関係 → [README.md](README.md)

## 目次

- [目的](#目的)
- [全体構成](#全体構成)
- [アーキテクチャ原則](#アーキテクチャ原則)
- [Collector Job](#collector-job)
- [Data Repository の更新](#data-repository-の更新)
- [CI Validation](#ci-validation)
- [Database Builder Job](#database-builder-job)
- [API Server](#api-server)
- [プロセスの独立性](#プロセスの独立性)
- [定期実行](#定期実行)
- [デプロイメント](#デプロイメント)
- [ログ・監視](#ログ監視)
- [セキュリティ](#セキュリティ)
- [将来拡張](#将来拡張)
- [v0.1 の確定事項](#v01-の確定事項)

## 目的

地方議会会議録の収集、変換、保存、検索用データベース生成、API 配布を担うシステムのアーキテクチャを定義する。

Git リポジトリ上の Canonical JSON をデータの正本とし、SQLite および API レスポンスを派生データとして扱う。

システム全体を次の責務へ分離する。

- 地方議会サイトからのデータ収集
- Canonical Data への変換
- Git リポジトリへの保存
- データ品質検証
- SQLite 検索データベース生成
- HTTP API による配布

## 全体構成

データフローは一方向を基本とする。

```text
地方議会Webサイト
        ↓
   Collector Job
        ↓
   Parser / Normalizer
        ↓
     Validator
        ↓
 Canonical JSON生成
        ↓
 作業ブランチへ commit
        ↓
    Pull Request
        ↓
    CI Validation
        ↓
       merge
        ↓
 local-council-data
      main branch
        ↓
 Database Builder Job
        ↓
     SQLite生成
        ↓
     API Server
        ↓
       利用者
```

要約すると次のとおり。

```text
Web → Canonical Data → Git → SQLite → API
```

### リポジトリ構成

2 リポジトリ構成とする。

#### local-council-data

地方議会会議録データの正本を管理する。

責務:

- Canonical JSON の保存
- 自治体マスタの管理
- JSON Schema の管理
- Git 履歴による変更履歴の保存
- Pull Request によるデータ更新管理

```text
local-council-data/
├── schema/
│   ├── meeting.schema.json
│   └── municipalities.schema.json
│
├── master/
│   └── municipalities.json
│
└── data/
    └── ...
```

ディレクトリの詳細は [data.md](data.md) を参照する。

#### local-council-system

データ収集、変換、検証、SQLite 生成および API 提供を担う。

```text
local-council-system/
├── src/
│   └── local_council/
│       ├── collectors/
│       ├── parsers/
│       ├── normalizers/
│       ├── validators/
│       ├── exporters/
│       ├── loaders/
│       ├── db/
│       ├── api/
│       ├── services/
│       └── cli/
│
├── config/
│   └── sources/
│
├── var/                      # Git管理外。Collector実行時に生成
│   └── collection-state.json
│
└── tests/
```

`var/collection-state.json` の意味は [ingest-sync.md](ingest-sync.md) を参照する。

## アーキテクチャ原則

### Git を正本とする

```text
Canonical JSON  = Source of Truth
検索用 SQLite   = Derived Search Database
API Response    = Derived View
```

収集処理のための作業用 SQLite も正本ではない。削除・再作成してよい。

### 検索用 SQLite へ収集結果を直接書き込まない

Collector、Parser、Normalizer は、API が読む検索用 SQLite を直接更新してはならない。

禁止する構成:

```text
Collector → 検索用SQLite → API
```

採用する構成:

```text
Collector → Canonical JSON → Git → Database Builder → 検索用SQLite
```

#### 作業用 SQLite

収集・変換を容易にするための作業用 SQLite は許可する。

用途の例:

- FETCH した HTML、PDF 等の原資料の一時保存
- PARSE / NORMALIZE の中間データ
- ジョブ内の重複排除や処理再開の補助

制約:

- 正本ではない
- API Server はこれを読まない
- Database Builder の入力ではない
- 検索用 SQLite とファイルを共有してはならない
- Canonical JSON として EXPORT できない状態を正本として扱ってはならない

### プロセスを分離する

次の 3 プロセスを独立させる。1 つの常駐プロセスに統合しない。

```text
Collector Job
Database Builder Job
API Server
```

| プロセス | 種類 | 役割 |
| --- | --- | --- |
| Collector Job | 定期バッチ | Web → Discover → Fetch → Parse → Normalize → Validate → Canonical JSON → Pull Request |
| Database Builder Job | バッチ | Git → Load → Validate → SQLite Build → Publish |
| API Server | 常駐 | HTTP Request → Query SQLite → JSON Response |

### 各プロセスは再実行可能とする

同一入力に対する処理は可能な限り決定論的とする。

Collector の再実行によって実質的な変更がなければ Git 差分を発生させない。

Database Builder は Canonical JSON から SQLite を何度でも再生成できなければならない。

## Collector Job

地方議会サイトから会議録を取得する定期バッチ。処理段階は次とする。

```text
DISCOVER → FETCH → PARSE → NORMALIZE → VALIDATE → EXPORT
```

収集範囲（初回同期、増分同期、lookback）は [ingest-sync.md](ingest-sync.md) が定義する。

### DISCOVER

対象自治体のサイトから取得対象の会議を発見する。結果として、収集元識別子および取得 URL を生成する。

### FETCH

HTML、PDF またはその他の原資料を取得する。

HTTP アクセスでは次を考慮する。

- Timeout
- Retry
- Rate Limit
- User-Agent
- HTTP ステータス
- robots.txt
- 利用規約

取得した原資料は、そのジョブ内で PARSE 入力として扱う。

v0.1 では、HTML や PDF のバイト列を `local-council-data` へ永続保存しない。正本リポジトリが保持するのは Canonical JSON と原典 URL であり、原資料そのものではない。

原資料を作業用 SQLite またはローカルキャッシュへ置いて PARSE を再実行することは許可する。ただしそれらは正本ではなく、Lookback 時は原則として再取得・再解析する。

### PARSE

取得した原資料から次を抽出する。

- 会議情報
- 開催日
- 会議名
- 会期
- 発言者
- 発言本文
- 発言順
- その他取得可能なメタデータ

### NORMALIZE

収集元固有の表現を Canonical Data Model へ変換する。Normalizer は原資料の意味を変更してはならない。

### VALIDATE

Canonical JSON 生成前または生成後にデータ品質検証を行う。

### EXPORT

Canonical JSON として data repository の working tree へ出力する。

作業用 SQLite の内容を EXPORT してはならない。EXPORT の対象は Canonical Data Model に変換済みの会議データのみとする。

## Data Repository の更新

データ更新は原則として Pull Request 方式とする。Collector Job が main branch へ直接 push してはならない。

```text
Collector Job
    ↓
変更検出
    ├── 変更なし → 終了
    └── 変更あり
            ↓
        作業ブランチ作成
            ↓
        Canonical JSON更新
            ↓
        commit → push → Pull Request
```

PR 方式を採用する理由:

- Parser 不具合による大量誤更新を防止する
- Web サイト仕様変更による異常データを検出する
- CI による機械検証を可能にする
- 必要に応じて人間が差分を確認できる
- Git 履歴の品質を維持する

通常更新については、CI Validation をすべて通過した場合に自動マージ可能とする。異常を検出した場合は自動マージを禁止する。

```text
PR → CI → 正常 → Auto Merge
```

## CI Validation

Pull Request に対し、最低限次を検証する。

### JSON 構文

すべての JSON が正しい JSON として解析可能であること。

### JSON Schema

Canonical JSON が定義済み JSON Schema に適合すること。

### ID 重複

`meeting.id` および `speech.id` が重複していないこと。公開 ID の生成規則は [id.md](id.md) を参照する。

### 自治体参照

`municipalityCode` が自治体マスタに存在すること。

### 発言順

同一 Meeting 内で `speech.order` が重複していないこと。

### 必須値

仕様上必須の次等が存在すること。

```text
meeting.id
meeting.municipalityCode
meeting.date
speech.id
speech.order
speech.speaker.name
speech.text
```

### 異常件数検知

既存データを更新した際、件数の急激な変化を検出する。

例: 旧発言数 350 が新発言数 3 になった場合は警告または CI failure とする。具体的な閾値は運用開始後に調整する。

### 空データ検知

既存会議が突然 `speeches = []` になった場合は原則として異常とする。

## Database Builder Job

data repository の main branch を入力として SQLite を生成する。

```text
Checkout / Pull
    ↓
JSON Schema Validation
    ↓
Create Temporary SQLite
    ↓
Load municipalities / meetings / speeches
    ↓
Create Indexes
    ↓
Integrity Check
    ↓
Publish SQLite
```

SQLite は一時ファイルとして生成し、完全に生成できた後に本番用 SQLite と置換する。

禁止する方式:

```text
本番SQLite → その場で全テーブル削除 → ロード途中で失敗
```

推奨方式:

```text
database.new.sqlite → 全構築成功 → atomic replacement → database.sqlite
```

### SQLite 再構築方針

v0.1 では全再構築を標準方式とする。差分更新は v0.1 の必須要件としない。

```text
Canonical JSON → SQLiteを新規生成 → 全データロード
```

全再構築では次を考慮する必要がない。

- 削除された JSON の追跡
- UPDATE 判定
- Speech / Meeting 削除
- 部分更新失敗時の整合性回復
- 差分ロード履歴
- Git commit と DB 状態の対応管理

SQLite が Canonical JSON から再生成可能であるため、初期段階では単純性を優先する。

全再構築時間が運用上問題となった場合に限り、差分更新方式を追加する。将来的に `build --full` と `build --incremental` の両方式を実装できる構造とする。`--full` は常に基準実装として維持する。

テーブル定義は [data.md](data.md) を参照する。

## API Server

FastAPI を使用する。SQLite を原則として読み取り専用で利用する。

提供する主要 API:

```text
GET /api/meeting_list
GET /api/meeting
GET /api/speech
```

エンドポイントの契約は [api.md](api.md) が定義する。

API Server は次を行わない。

- 地方議会サイトへのアクセス
- Canonical JSON の変更
- Git 操作
- SQLite データの業務的更新
- Parser の実行

責務は次に限定する。

```text
Request → Validation → SQLite Query → Response Mapping → JSON
```

## プロセスの独立性

依存方向は次とする。

```text
Collector Job     → Canonical Data
Database Builder  → Canonical Data
API Server        → SQLite
```

- API Server は Collector へ依存しない
- Collector は API Server へ依存しない
- Database Builder は API Server へ依存しない

各プロセスは可能な限り独立して実行可能とする。

プロセス分離により、次の性質を確保する。

| 障害 | 影響しないもの |
| --- | --- |
| Collector Job の失敗 | 既存 API は稼働し続ける |
| 新しい SQLite 生成の失敗 | 既存 SQLite を継続利用し、API は稼働し続ける |
| API Server の障害 | Canonical Data および Collector 処理 |

## 定期実行

Collector は CLI アプリケーションとして実装し、外部スケジューラから実行可能とする。

```bash
python -m local_council collect --all

python -m local_council collect --municipality 341002

python -m local_council collect --adapter voices
```

Database Builder:

```bash
python -m local_council build-db
```

API Server:

```bash
uvicorn local_council.api.app:app
```

スケジュール機能そのものはアプリケーションコードへ組み込まない。外部から GitHub Actions、cron、systemd timer、その他 CI/CD 基盤を利用して起動する。

## デプロイメント

v0.1 では GitHub を利用した構成を第一候補とする。

Collector の `var/collection-state.json` は Git 管理外のため、実行環境が毎回消える GitHub-hosted runner だけで収集する場合は、このファイルをジョブ間で復元するか、`var/` が残る環境で Collector を実行する。

```text
GitHub Actions
      │
      ├── Scheduled Collector
      ├── PR Validation
      └── Database Build

API Server は別途常駐環境へデプロイする
```

概念構成:

```text
GitHub
├── local-council-data
└── local-council-system
        ↓
CI/CD
├── Collector Job
├── Validation
└── DB Builder
        ↓
API Hosting
├── FastAPI
└── SQLite
```

具体的なホスティング環境は本仕様では固定しない。

## ログ・監視

各プロセスは標準出力へ構造化ログを出力できることが望ましい。最低限次を記録する。

Collector:

```text
municipalityCode
sourceSystem
meeting count
success count
failure count
duration
```

Database Builder:

```text
municipality count
meeting count
speech count
build duration
database size
```

API:

```text
request path
status code
duration
```

個人情報に該当し得る不要な情報はログへ出力しない。

## セキュリティ

### API

v0.1 では読み取り専用 API とする。データ更新用 HTTP API は提供しない。

### Git 認証情報

Collector Job が Pull Request を作成するために使用する GitHub Token 等は Secret として管理する。ソースコードまたは Canonical JSON へ保存してはならない。

### 外部サイト

Collector は外部サイトから取得した HTML 等を信頼せず、Parser 入力として扱う。取得したデータをコードとして評価してはならない。

## 将来拡張

v0.1 では導入しないが、追加可能とする。

### 差分 Database Build

Git diff を利用した SQLite 差分更新。

### 並列収集

自治体単位で Collector Job を並列化する。

```text
341002 Job
342025 Job
...
```

### キュー方式

自治体数の増加に応じて、Scheduler → Queue → Collector Worker へ移行可能とする。

### 検索基盤変更

SQLite による検索性能が不足した場合、SQLite → FTS → 外部検索エンジン へ変更可能とする。API 外部仕様は可能な限り維持する。

### API 複数インスタンス

SQLite が読み取り専用であるため、同一 SQLite 成果物を複数 API Server へ配布する構成も可能とする。

## v0.1 の確定事項

```text
リポジトリ:     2リポジトリ
データ正本:     Git上のCanonical JSON
データ更新:     Pull Request方式
通常更新:       CI成功時の自動マージを許容
収集:           定期実行可能なCollector Job
DB生成:         独立したDatabase Builder Job
検索DB:         SQLite（Canonical JSONから全再構築）
作業用DB:       Collector内のSQLiteを許可する。正本およびAPI入力ではない
収集状態:       var/collection-state.json（Git管理外、自治体ごとの lastSuccessfulSync）
DB更新:         原則として全再構築
API:            FastAPI
API実行:        常駐プロセス
検索:           SQLite LIKEを基本とする
プロセス:       Collector / Database Builder / API Server の3分離
```

したがって、本システムの基本構造は次とする。

```text
地方議会Webサイト
        ↓
Collector Job
        ↓
Canonical JSON
        ↓
Pull Request
        ↓
CI Validation
        ↓
Git main
        ↓
Database Builder Job
        ↓
SQLite
        ↓
FastAPI
        ↓
利用者
```

Canonical Data を中心に各プロセスを疎結合とし、収集、データ保存、検索 DB 生成および API 配布の障害を相互に分離する。
