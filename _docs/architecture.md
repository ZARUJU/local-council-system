# 地方議会会議録システム アーキテクチャ仕様書

## 目次

1. 目的
2. 全体構成
3. リポジトリ構成
4. アーキテクチャ原則
5. プロセス構成
6. Collector Job
7. Data Repository更新方式
8. CI Validation
9. Database Builder Job
10. SQLite再構築方針
11. API Server
12. プロセス間の依存関係
13. 障害分離
14. 定期実行方式
15. デプロイメント構成
16. ログ・監視
17. セキュリティ
18. 将来拡張
19. v0.1の確定事項

# 1. 目的

本仕様書は、地方議会会議録の収集、変換、保存、検索用データベース生成およびAPI配布を担うシステムのアーキテクチャを定義する。

本システムでは、Gitリポジトリ上のCanonical JSONをデータの正本とし、SQLiteおよびAPIレスポンスを派生データとして扱う。

システム全体を以下の責務へ分離する。

* 地方議会サイトからのデータ収集
* Canonical Dataへの変換
* Gitリポジトリへの保存
* データ品質検証
* SQLite検索データベース生成
* HTTP APIによる配布

# 2. 全体構成

システム全体は以下の構成とする。

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
 作業ブランチへcommit
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

データフローは一方向を基本とする。

```text
Web
→ Canonical Data
→ Git
→ SQLite
→ API
```

# 3. リポジトリ構成

本システムは2リポジトリ構成とする。

## 3.1 local-council-data

地方議会会議録データの正本を管理する。

主な責務:

* Canonical JSONの保存
* 自治体マスタの管理
* JSON Schemaの管理
* Git履歴による変更履歴の保存
* Pull Requestによるデータ更新管理

例:

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

## 3.2 local-council-system

データ収集、変換、検証、SQLite生成およびAPI提供を担う。

例:

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
└── tests/
```

# 4. アーキテクチャ原則

## 4.1 Gitを正本とする

Canonical JSONを唯一の正本とする。

```text
Canonical JSON
= Source of Truth
```

SQLiteは正本ではない。

```text
SQLite
= Derived Search Database
```

APIレスポンスも正本ではない。

```text
API Response
= Derived View
```

## 4.2 SQLiteへ直接収集結果を書き込まない

Collector、Parser、NormalizerはSQLiteを直接更新してはならない。

禁止する構成:

```text
Collector
    ↓
SQLite
    ↓
API
```

採用する構成:

```text
Collector
    ↓
Canonical JSON
    ↓
Git
    ↓
Database Builder
    ↓
SQLite
```

## 4.3 プロセスを分離する

以下の3プロセスを独立させる。

```text
Collector Job
Database Builder Job
API Server
```

1つの常駐プロセスに統合しない。

## 4.4 各プロセスは再実行可能とする

同一入力に対する処理は可能な限り決定論的とする。

Collectorの再実行によって実質的な変更がなければGit差分を発生させない。

Database BuilderはCanonical JSONからSQLiteを何度でも再生成できなければならない。

# 5. プロセス構成

## 5.1 Collector Job

定期実行されるバッチプロセス。

役割:

```text
Web
→ Discover
→ Fetch
→ Parse
→ Normalize
→ Validate
→ Canonical JSON
→ Pull Request
```

## 5.2 Database Builder Job

Canonical JSONからSQLiteを生成するバッチプロセス。

役割:

```text
Git Repository
→ Load
→ Validate
→ SQLite Build
→ Publish Database
```

## 5.3 API Server

SQLiteを読み取り、HTTP APIを提供する常駐プロセス。

役割:

```text
HTTP Request
→ Query SQLite
→ Format Response
→ JSON Response
```

# 6. Collector Job

Collector Jobは地方議会サイトから会議録を取得する。

処理段階は以下とする。

```text
DISCOVER
FETCH
PARSE
NORMALIZE
VALIDATE
EXPORT
```

## 6.1 DISCOVER

対象自治体のサイトから取得対象の会議を発見する。

結果として、収集元識別子および取得URLを生成する。

## 6.2 FETCH

HTML、PDFまたはその他の原資料を取得する。

HTTPアクセスでは以下を考慮する。

* Timeout
* Retry
* Rate Limit
* User-Agent
* HTTPステータス
* robots.txt
* 利用規約

## 6.3 PARSE

取得した原資料から以下を抽出する。

* 会議情報
* 開催日
* 会議名
* 会期
* 発言者
* 発言本文
* 発言順
* その他取得可能なメタデータ

## 6.4 NORMALIZE

収集元固有の表現をCanonical Data Modelへ変換する。

Normalizerは原資料の意味を変更してはならない。

## 6.5 VALIDATE

Canonical JSON生成前または生成後にデータ品質検証を行う。

## 6.6 EXPORT

Canonical JSONとしてdata repositoryのworking treeへ出力する。

# 7. Data Repository更新方式

データ更新は原則としてPull Request方式とする。

Collector Jobがmain branchへ直接pushしてはならない。

処理フロー:

```text
Collector Job
    ↓
変更検出
    ↓
変更なし
    └─ 終了

変更あり
    ↓
作業ブランチ作成
    ↓
Canonical JSON更新
    ↓
commit
    ↓
push
    ↓
Pull Request作成
```

## 7.1 PR方式を採用する理由

以下を目的とする。

* Parser不具合による大量誤更新を防止する
* Webサイト仕様変更による異常データを検出する
* CIによる機械検証を可能にする
* 必要に応じて人間が差分を確認できる
* Git履歴の品質を維持する

## 7.2 自動マージ

通常更新については、CI Validationをすべて通過した場合に自動マージ可能とする。

```text
PR
 ↓
CI
 ↓
正常
 ↓
Auto Merge
```

異常を検出した場合は自動マージを禁止する。

# 8. CI Validation

Pull Requestに対し、最低限以下を検証する。

## 8.1 JSON構文

すべてのJSONが正しいJSONとして解析可能であること。

## 8.2 JSON Schema

Canonical JSONが定義済みJSON Schemaに適合すること。

## 8.3 ID重複

以下が重複していないこと。

```text
meeting.id
speech.id
```

## 8.4 自治体参照

`municipalityCode`が自治体マスタに存在すること。

## 8.5 発言順

同一Meeting内で`speech.order`が重複していないこと。

## 8.6 必須値

仕様上必須の以下等が存在すること。

```text
meeting.id
meeting.municipalityCode
meeting.date
speech.id
speech.order
speech.speaker.name
speech.text
```

## 8.7 異常件数検知

既存データを更新した際、件数の急激な変化を検出する。

例:

```text
旧発言数: 350
新発言数: 3
```

のような場合は警告またはCI failureとする。

具体的な閾値は運用開始後に調整する。

## 8.8 空データ検知

既存会議が突然、

```text
speeches = []
```

になった場合は原則として異常とする。

# 9. Database Builder Job

Database Builder Jobはdata repositoryのmain branchを入力としてSQLiteを生成する。

処理:

```text
Checkout / Pull
    ↓
JSON Schema Validation
    ↓
Create Temporary SQLite
    ↓
Load municipalities
    ↓
Load meetings
    ↓
Load speeches
    ↓
Create Indexes
    ↓
Integrity Check
    ↓
Publish SQLite
```

SQLiteは一時ファイルとして生成し、完全に生成できた後に本番用SQLiteと置換する。

禁止する方式:

```text
本番SQLite
    ↓
その場で全テーブル削除
    ↓
ロード途中で失敗
```

推奨方式:

```text
database.new.sqlite
        ↓
全構築成功
        ↓
atomic replacement
        ↓
database.sqlite
```

# 10. SQLite再構築方針

v0.1では全再構築を標準方式とする。

```text
Canonical JSON
      ↓
SQLiteを新規生成
      ↓
全データロード
```

差分更新はv0.1の必須要件としない。

## 10.1 全再構築を採用する理由

全再構築では以下を考慮する必要がない。

* 削除されたJSONの追跡
* UPDATE判定
* Speech削除
* Meeting削除
* 部分更新失敗時の整合性回復
* 差分ロード履歴
* Git commitとDB状態の対応管理

SQLiteがCanonical JSONから再生成可能であるため、初期段階では単純性を優先する。

## 10.2 将来の差分更新

全再構築時間が運用上問題となった場合に限り、差分更新方式を追加する。

将来的に、

```text
build --full
build --incremental
```

の両方式を実装できる構造とする。

ただし、`--full`は常に基準実装として維持する。

# 11. API Server

API ServerにはFastAPIを使用する。

API ServerはSQLiteを原則として読み取り専用で利用する。

提供する主要API:

```text
GET /api/meeting_list
GET /api/meeting
GET /api/speech
```

API Serverは以下を行わない。

* 地方議会サイトへのアクセス
* Canonical JSONの変更
* Git操作
* SQLiteデータの業務的更新
* Parserの実行

API Serverの責務は以下に限定する。

```text
Request
↓
Validation
↓
SQLite Query
↓
Response Mapping
↓
JSON
```

# 12. プロセス間の依存関係

依存方向は以下とする。

```text
Collector Job
     ↓
Canonical Data

Database Builder
     ↓
Canonical Data

API Server
     ↓
SQLite
```

API ServerはCollectorへ依存しない。

CollectorはAPI Serverへ依存しない。

Database BuilderはAPI Serverへ依存しない。

各プロセスは可能な限り独立して実行可能とする。

# 13. 障害分離

プロセス分離により、以下の性質を確保する。

## 13.1 Collector障害

Collector Jobが失敗しても既存APIは稼働し続ける。

```text
Collector ×
API ○
```

## 13.2 Database Builder障害

新しいSQLiteの生成に失敗した場合、既存SQLiteを継続利用する。

```text
New Build ×
Existing DB ○
API ○
```

## 13.3 API障害

API Server障害はCanonical DataおよびCollector処理へ影響しない。

# 14. 定期実行方式

CollectorはCLIアプリケーションとして実装し、外部スケジューラから実行可能とする。

例:

```bash
python -m local_council collect --all
```

自治体単位:

```bash
python -m local_council collect \
  --municipality 341002
```

特定Adapter:

```bash
python -m local_council collect \
  --adapter voices
```

Database BuilderもCLIとして提供する。

```bash
python -m local_council build-db
```

API Server:

```bash
uvicorn local_council.api.app:app
```

スケジュール機能そのものはアプリケーションコードへ組み込まない。

外部から、

* GitHub Actions
* cron
* systemd timer
* その他CI/CD基盤

等を利用して起動する。

# 15. デプロイメント構成

v0.1ではGitHubを利用した構成を第一候補とする。

例:

```text
GitHub Actions
      │
      ├── Scheduled Collector
      │
      ├── PR Validation
      │
      └── Database Build
```

API Serverは別途常駐環境へデプロイする。

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

# 16. ログ・監視

各プロセスは標準出力へ構造化ログを出力できることが望ましい。

最低限以下を記録する。

## Collector

```text
municipalityCode
sourceSystem
meeting count
success count
failure count
duration
```

## Database Builder

```text
municipality count
meeting count
speech count
build duration
database size
```

## API

```text
request path
status code
duration
```

個人情報に該当し得る不要な情報はログへ出力しない。

# 17. セキュリティ

## 17.1 API

v0.1では読み取り専用APIとする。

データ更新用HTTP APIは提供しない。

## 17.2 Git認証情報

Collector JobがPull Requestを作成するために使用するGitHub Token等はSecretとして管理する。

ソースコードまたはCanonical JSONへ保存してはならない。

## 17.3 外部サイト

Collectorは外部サイトから取得したHTML等を信頼せず、Parser入力として扱う。

取得したデータをコードとして評価してはならない。

# 18. 将来拡張

以下は将来的に追加可能とする。

## 18.1 差分Database Build

Git diffを利用したSQLite差分更新。

## 18.2 並列収集

自治体単位でCollector Jobを並列化する。

```text
341002 Job
342025 Job
...
```

## 18.3 キュー方式

自治体数の増加に応じて、

```text
Scheduler
 ↓
Queue
 ↓
Collector Worker
```

へ移行可能とする。

ただしv0.1では導入しない。

## 18.4 検索基盤変更

SQLiteによる検索性能が不足した場合、

```text
SQLite
 ↓
FTS
 ↓
外部検索エンジン
```

へ変更可能とする。

API外部仕様は可能な限り維持する。

## 18.5 API複数インスタンス

SQLiteが読み取り専用であるため、同一SQLite成果物を複数API Serverへ配布する構成も可能とする。

# 19. v0.1の確定事項

v0.1では以下を基本アーキテクチャとして採用する。

```text
リポジトリ:
    2リポジトリ

データ正本:
    Git上のCanonical JSON

データ更新:
    Pull Request方式

通常更新:
    CI成功時の自動マージを許容

収集:
    定期実行可能なCollector Job

DB生成:
    独立したDatabase Builder Job

DB:
    SQLite

DB更新:
    原則として全再構築

API:
    FastAPI

API実行:
    常駐プロセス

検索:
    SQLite LIKEを基本とする

プロセス:
    Collector
    Database Builder
    API Server
    の3分離
```

したがって、本システムの基本構造は以下とする。

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

Canonical Dataを中心に各プロセスを疎結合とし、収集、データ保存、検索DB生成およびAPI配布の障害を相互に分離する。
