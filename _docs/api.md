# 検索 API

この文書は、横断検索用 HTTP API の外部契約を定義します。Canonical とのフィールド対応は [data.md](data.md)、公開 ID の形は [id.md](id.md) を参照してください。いま公開しているエンドポイントは [status.md](status.md) を正とします。

関連:

- 実装状況 → [status.md](status.md)
- API Server の責務とプロセス上の位置づけ → [architecture.md](architecture.md)
- Canonical / SQLite / API のマッピング → [data.md](data.md)
- `meetingID` / `speechID` → [id.md](id.md)
- 文書の読み順と優先関係 → [README.md](README.md)

## 目次

- [目的](#目的)
- [設計方針](#設計方針)
- [基本仕様](#基本仕様)
- [API 一覧](#api-一覧)
- [共通検索パラメータ](#共通検索パラメータ)
- [検索条件の評価規則](#検索条件の評価規則)
- [会議単位簡易出力](#会議単位簡易出力)
- [会議単位出力](#会議単位出力)
- [発言単位出力](#発言単位出力)
- [ページング](#ページング)
- [ソート順](#ソート順)
- [エラー仕様](#エラー仕様)
- [HTTP 仕様](#http-仕様)
- [内部データモデルとの関係](#内部データモデルとの関係)
- [将来拡張](#将来拡張)

## 目的

地方公共団体の議会が公開する会議録を横断的に検索および取得するための HTTP API を提供する。

基本設計は国立国会図書館「国会会議録検索システム検索用API」を参考とする。国会会議録検索 API と同様に、検索条件は原則として共通とし、利用目的に応じて次の 3 種類の出力形式を提供する。

- 会議単位簡易出力
- 会議単位出力
- 発言単位出力

地方議会固有の検索条件として、自治体、自治体コードおよび都道府県を追加する。

## 設計方針

### 国会会議録 API との類似性

国会会議録 API 利用者が理解しやすいよう、可能な範囲で次を踏襲する。

- HTTP GET による検索
- `meeting_list`、`meeting`、`speech` の 3 種類
- `startRecord` による開始位置指定
- `maximumRecords` による件数指定
- `any` による発言本文検索
- `speaker` による発言者検索
- `nameOfMeeting` による会議名検索
- `from` および `until` による開催日検索
- `speechNumber` による発言番号検索
- `speakerPosition` による肩書き検索
- `speakerGroup` による会派検索
- `speechID` による発言の一意検索
- 開催日の新しい順を標準ソート順とする

国会会議録 API では、`any` に複数語を指定した場合は AND 検索、`nameOfMeeting` および `speaker` では OR 検索となる。本 API でもこの規則を踏襲する。

### 地方議会向け変更

国会固有の次の概念は採用しない。

- 院名
- 国会回次
- 国会号数
- 追録・附録
- 目次・索引
- 議事冒頭・本文区分

代わりに次を導入する。

- 都道府県
- 自治体
- 全国地方公共団体コード
- 会期・定例会等を表す session
- 地方議会固有の会議名

## 基本仕様

ベースパスは `/api`。文字コードは UTF-8。応答形式は JSON のみ。検索リクエストには HTTP GET を使用する。

```http
GET /api/speech?any=学校給食&municipalityCode=341002
```

## API 一覧

### 会議単位簡易出力

```http
GET /api/meeting_list
```

検索条件に一致した会議のメタデータを返却する。発言本文は返却しない。発言条件によって会議がヒットした場合は、一致した発言の最低限の情報を含めることができる。

### 会議単位出力

```http
GET /api/meeting
```

検索条件に一致した会議と、当該会議に含まれるすべての発言を返却する。

### 発言単位出力

```http
GET /api/speech
```

検索条件に一致した発言のみを返却する。各発言には、それが属する会議および自治体の情報を付与する。

## 共通検索パラメータ

| パラメータ | 型 | 検索方法 | 説明 |
| --- | --- | --- | --- |
| `startRecord` | integer | - | 取得開始位置 |
| `maximumRecords` | integer | - | 最大取得件数 |
| `prefecture` | string | 部分一致 | 都道府県名 |
| `municipality` | string | 部分一致 | 自治体名 |
| `municipalityCode` | string | 完全一致 | 全国地方公共団体コード |
| `nameOfMeeting` | string | 部分一致 | 本会議・委員会等の会議名 |
| `session` | string | 部分一致 | 定例会・臨時会等の会期名称 |
| `any` | string | 部分一致 | 発言本文 |
| `speaker` | string | 部分一致 | 発言者名 |
| `from` | date | 範囲 | 開催日下限 |
| `until` | date | 範囲 | 開催日上限 |
| `speechNumber` | integer | 完全一致 | 会議内の発言番号 |
| `speakerPosition` | string | 部分一致 | 発言者肩書き |
| `speakerGroup` | string | 部分一致 | 会派等 |
| `speakerRole` | string | 部分一致 | 発言者役割 |
| `speechID` | string | 完全一致 | 発言 ID |
| `meetingID` | string | 完全一致 | 会議 ID |

少なくとも 1 つの実質的検索条件を指定しなければならない。`startRecord` および `maximumRecords` のみを指定したリクエストは検索条件とはみなさない。

## 検索条件の評価規則

### パラメータ間

異なる検索パラメータは AND 条件として評価する。

例: `municipality=広島市` かつ `any=学校給食` かつ `speaker=山田` は、自治体名に「広島市」を含み、発言本文に「学校給食」を含み、発言者名に「山田」を含むことを意味する。

### any

半角スペース区切りで複数語を指定した場合は AND 検索とする。

```text
any=学校給食 無償化
```

は次相当とする。

```text
speech LIKE '%学校給食%'
AND
speech LIKE '%無償化%'
```

### speaker

半角スペース区切りで複数語を指定した場合は OR 検索とする。

```text
speaker=田中 鈴木
```

は次相当とする。

```text
speaker LIKE '%田中%'
OR
speaker LIKE '%鈴木%'
```

### nameOfMeeting

半角スペース区切りで複数語を指定した場合は OR 検索とする。

```text
nameOfMeeting=総務 文教
```

は、「総務」または「文教」を含む会議を対象とする。

### その他の部分一致項目

`municipality`、`prefecture`、`session`、`speakerPosition`、`speakerGroup` および `speakerRole` は、入力文字列全体による部分一致とする。複数語構文は定義しない。

### 日付

日付は ISO 8601 の `YYYY-MM-DD` とする。`from` と `until` の両方を指定した場合は両端を含む。

```text
from <= meeting.date <= until
```

特定日の検索では同じ日を指定する。

```text
from=2026-09-10
until=2026-09-10
```

## 会議単位簡易出力

```http
GET /api/meeting_list
```

`maximumRecords` の範囲は 1～100、デフォルトは 30。

```json
{
  "numberOfRecords": 120,
  "numberOfReturn": 30,
  "startRecord": 1,
  "nextRecordPosition": 31,
  "meetingRecord": [
    {
      "meetingID": "9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311",
      "prefecture": "広島県",
      "municipality": "広島市",
      "municipalityCode": "341002",
      "session": "令和8年第3回定例会",
      "nameOfMeeting": "本会議",
      "date": "2026-09-10",
      "speechRecord": [
        {
          "speechID": "e5f1f604-cd64-5ac4-a6f4-7b2c9d8e1a20",
          "speechOrder": 42,
          "speaker": "山田太郎"
        }
      ],
      "meetingURL": "https://example.jp/...",
      "pdfURL": null
    }
  ]
}
```

`speechRecord` は発言に関する検索条件によってヒットした場合にのみ含めてもよい。発言本文は含めない。

## 会議単位出力

```http
GET /api/meeting
```

`maximumRecords` の範囲は 1～10、デフォルトは 3。

```json
{
  "numberOfRecords": 1,
  "numberOfReturn": 1,
  "startRecord": 1,
  "nextRecordPosition": null,
  "meetingRecord": [
    {
      "meetingID": "9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311",
      "prefecture": "広島県",
      "municipality": "広島市",
      "municipalityCode": "341002",
      "session": "令和8年第3回定例会",
      "nameOfMeeting": "本会議",
      "date": "2026-09-10",
      "speechRecord": [
        {
          "speechID": "c8d9e0f1-2a3b-5c4d-8e5f-6a7b8c9d0e1f",
          "speechOrder": 1,
          "speaker": "議長",
          "speakerYomi": null,
          "speakerGroup": null,
          "speakerPosition": "議長",
          "speakerRole": null,
          "speech": "ただいまから会議を開きます。",
          "startPage": null,
          "speechURL": null
        }
      ],
      "meetingURL": "https://example.jp/...",
      "pdfURL": null
    }
  ]
}
```

検索条件に一致した発言だけではなく、その会議の全発言を返却する。

## 発言単位出力

```http
GET /api/speech
```

`maximumRecords` の範囲は 1～100、デフォルトは 30。

```json
{
  "numberOfRecords": 123,
  "numberOfReturn": 30,
  "startRecord": 1,
  "nextRecordPosition": 31,
  "speechRecord": [
    {
      "speechID": "e5f1f604-cd64-5ac4-a6f4-7b2c9d8e1a20",
      "meetingID": "9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311",
      "prefecture": "広島県",
      "municipality": "広島市",
      "municipalityCode": "341002",
      "session": "令和8年第3回定例会",
      "nameOfMeeting": "本会議",
      "date": "2026-09-10",
      "speechOrder": 42,
      "speaker": "山田太郎",
      "speakerYomi": null,
      "speakerGroup": "○○会",
      "speakerPosition": "議員",
      "speakerRole": null,
      "speech": "学校給食の無償化について質問します。",
      "startPage": null,
      "speechURL": null,
      "meetingURL": "https://example.jp/...",
      "pdfURL": null
    }
  ]
}
```

発言単位 API では、利用者が 1 件のレコードだけ取得しても意味を解釈できるよう、会議情報および自治体情報を非正規化して含める。

## ページング

`startRecord` は 1 始まりとする。`startRecord=1` が先頭レコードを表す。

レスポンスには次を含める。

```text
numberOfRecords
numberOfReturn
startRecord
nextRecordPosition
```

最終ページでは `"nextRecordPosition": null` とする。

## ソート順

デフォルトソート順は次のとおりとする。

```text
meeting.date DESC
meeting.id ASC
speech.order ASC
```

すなわち、開催日の新しい会議を優先する。同日の会議については一意かつ安定した順序となるよう ID で補助ソートする。発言単位出力では同一会議内の発言順を維持する。

## エラー仕様

エラーは JSON で返却する。

```json
{
  "message": "Invalid request.",
  "details": [
    "maximumRecords must be between 1 and 100."
  ]
}
```

| 状況 | Status |
| --- | ---: |
| 正常 | 200 |
| パラメータ不正 | 400 |
| 該当リソースなし | 原則 200、0 件 |
| サーバー内部エラー | 500 |
| 一時利用不能 | 503 |

検索結果 0 件はエラーとせず、次のように返却する。

```json
{
  "numberOfRecords": 0,
  "numberOfReturn": 0,
  "startRecord": 1,
  "nextRecordPosition": null,
  "speechRecord": []
}
```

## HTTP 仕様

レスポンス Content-Type は `application/json; charset=utf-8`。

API は読み取り専用とする。HTTP メソッドは GET のみ公開する。認証は要求しない。CORS の許可範囲は運用環境で別途定める。

## 内部データモデルとの関係

API レスポンス形式は Canonical Data Model そのものではない。Canonical Data Model を基礎として、利用目的に応じて表示粒度を変換する。フィールド対応表は [data.md](data.md) を参照する。

```text
Canonical Data
      ↓
SQLite
      ↓
API View
 ├─ meeting_list
 ├─ meeting
 └─ speech
```

API では利便性のため、自治体情報や会議情報を発言レコードへ重複して含めることを許容する。

## 将来拡張

XML 出力、全文検索エンジン、書き込み API など、いま実装しないものは [status.md](status.md) を正とする。

検索性能が不足した場合は、外部 API 仕様を維持したまま SQLite の検索実装を FTS 等へ置き換える。外部インターフェースと内部検索方式を分離する。
