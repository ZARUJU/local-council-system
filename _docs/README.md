# 仕様書

本ディレクトリは local-council-system の仕様を定義します。実装の正はコードではなく、ここに書いた内容です。

最初にリポジトリ直下の [README.md](../README.md) を読み、必要に応じて下の文書へ進んでください。

## 文書一覧

| 文書 | 定義すること | 読者 |
| --- | --- | --- |
| [architecture.md](architecture.md) | システム境界、プロセス分離、CI、デプロイ、障害分離 | 実装・運用の全体像を把握したいとき |
| [data.md](data.md) | Canonical Data Model、Git 保存形式、SQLite、各層のマッピング | データを永続化・変換するとき |
| [id.md](id.md) | Meeting / Speech の公開 ID（UUIDv5） | ID を生成・維持するとき |
| [ingest-sync.md](ingest-sync.md) | Collection State、初回同期、増分同期、lookback | Collector を実装・運用するとき |
| [api.md](api.md) | HTTP API の契約（パラメータ、レスポンス、エラー） | API を実装・利用するとき |

## 推奨する読み順

```text
README.md
    ↓
architecture.md     何がどこまでを担うか
    ↓
data.md             データをどう表現し、どこに置くか
    ↓
id.md               公開 ID をどう決めるか
    ↓
ingest-sync.md      いつ、どこから、どこまで取り直すか
    ↓
api.md              外部にどう見せるか
```

アーキテクチャだけ読めばシステムの形は分かります。データと API を実装するときは、その手前の文書を先に読んでください。公開 ID はデータモデルの一部ですが、生成規則が独立して長いため別文書にしています。

## 文書間で重なる記述の優先

同じ事柄を複数の文書が触れる場合、次を正とします。他文書の該当箇所は要約または例です。

| 事柄 | 正とする文書 |
| --- | --- |
| プロセス分離、CI、デプロイ、障害分離 | [architecture.md](architecture.md) |
| Canonical フィールドの意味、Git 配置、SQLite スキーマ、層間マッピング | [data.md](data.md) |
| 公開 ID の生成・維持・禁止事項 | [id.md](id.md) |
| 収集範囲、`lastSuccessfulSync`、lookback、同期の成否 | [ingest-sync.md](ingest-sync.md) |
| リクエスト、レスポンス、ページング、HTTP エラー | [api.md](api.md) |

例:

- Canonical JSON の `meeting.id` が UUIDv5 であることは [id.md](id.md) が正です。[data.md](data.md) の JSON 例と [api.md](api.md) の `meetingID` はそれに合わせます。
- 検索用 SQLite を v0.1 で全再構築することは [architecture.md](architecture.md) が正です。[data.md](data.md) は、将来の差分更新も載せられる構造であることを述べます。
- `/api/speech` のフィールド名とページングは [api.md](api.md) が正です。[data.md](data.md) の API 例は対応関係の説明用です。

## v0.1 で共通する前提

各文書の末尾に文書固有の確定事項があります。システム全体としては次を前提にします。

- 正本は Git 上の Canonical JSON。SQLite と API は派生
- 収集、DB 生成、API 提供は 3 プロセスに分離
- データ更新は Pull Request。通常更新は CI 成功時の自動マージを許容
- 検索用 SQLite は Canonical JSON から全再構築
- API は FastAPI、読み取り専用、HTTP GET、JSON
- 公開 ID は決定論的な UUIDv5。ランダム ID は使わない
