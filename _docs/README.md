# 仕様書

本ディレクトリは local-council-system の仕様を定義します。実装の正はコードではなく、ここに書いた内容です。

最初にリポジトリ直下の [README.md](../README.md) を読み、必要に応じて下の文書へ進んでください。いま動く範囲と、まだやらない範囲は [status.md](status.md) だけを正とします。

## 文書一覧

| 文書 | 定義すること | 読者 |
| --- | --- | --- |
| [status.md](status.md) | いま実装されている範囲、未実装、採用しないもの | 現状を知りたいとき |
| [architecture.md](architecture.md) | システム境界、プロセス分離、CI、デプロイ、障害分離 | 実装・運用の全体像を把握したいとき |
| [data.md](data.md) | Canonical Data Model、Git 保存形式、SQLite、各層のマッピング | データを永続化・変換するとき |
| [id.md](id.md) | Meeting / Speech の公開 ID（UUIDv5） | ID を生成・維持するとき |
| [ingest-sync.md](ingest-sync.md) | Collection State、初回同期、増分同期、lookback | Collector を実装・運用するとき |
| [sources.md](sources.md) | 自治体ごとの公開形態、実装タイプ、収集可否 | Adapter を追加・見送るとき |
| [cli.md](cli.md) | CLI のコマンド体系、起動方法、終了コード | ジョブを起動・試行するとき |
| [api.md](api.md) | HTTP API の契約（パラメータ、レスポンス、エラー） | API を実装・利用するとき |

## 推奨する読み順

```text
README.md
    ↓
status.md           いまどこまで実装されているか
    ↓
architecture.md     何がどこまでを担うか
    ↓
data.md             データをどう表現し、どこに置くか
    ↓
id.md               公開 ID をどう決めるか
    ↓
ingest-sync.md      いつ、どこから、どこまで取り直すか
    ↓
sources.md          どの自治体を、どの公開形態として扱うか
    ↓
cli.md              ジョブをどう起動するか
    ↓
api.md              外部にどう見せるか
```

アーキテクチャだけ読めばシステムの形は分かります。データと API を実装するときは、その手前の文書を先に読んでください。公開 ID はデータモデルの一部ですが、生成規則が独立して長いため別文書にしています。実装の有無や収集対象の広さは、各文書ではなく [status.md](status.md) に書きます。

## 文書間で重なる記述の優先

同じ事柄を複数の文書が触れる場合、次を正とします。他文書の該当箇所は要約または例です。

| 事柄 | 正とする文書 |
| --- | --- |
| いま実装されている範囲、未実装、採用しない機能 | [status.md](status.md) |
| プロセス分離、CI、デプロイ、障害分離 | [architecture.md](architecture.md) |
| Canonical フィールドの意味、Git 配置、SQLite スキーマ、層間マッピング | [data.md](data.md) |
| 公開 ID の生成・維持・禁止事項 | [id.md](id.md) |
| 収集範囲、`lastSuccessfulSync`、lookback、同期の成否 | [ingest-sync.md](ingest-sync.md) |
| 対象自治体、実装タイプ、収集してよい原資料 | [sources.md](sources.md) |
| CLI のサブコマンド、引数、終了コード、起動方法 | [cli.md](cli.md) |
| リクエスト、レスポンス、ページング、HTTP エラー | [api.md](api.md) |

例:

- Canonical JSON の `meeting.id` が UUIDv5 であることは [id.md](id.md) が正です。[data.md](data.md) の JSON 例と [api.md](api.md) の `meetingID` はそれに合わせます。
- 検索用 SQLite を全再構築することは [architecture.md](architecture.md) が正です。[data.md](data.md) は、将来の差分更新も載せられる構造であることを述べます。いま差分更新が未実装であることは [status.md](status.md) が正です。
- `/api/speech` のフィールド名とページングは [api.md](api.md) が正です。[data.md](data.md) の API 例は対応関係の説明用です。
- `collect --municipality` の引数と終了コードは [cli.md](cli.md) が正です。[architecture.md](architecture.md) の起動例はそれに合わせます。
- 対象自治体の収集可否は [sources.md](sources.md) が正です。Adapter が実装済みかどうかは [status.md](status.md) が正です。
