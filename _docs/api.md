# 地方議会会議録検索API仕様書

## 目次

1. 目的
2. 設計方針
3. 基本仕様
4. API一覧
5. 共通検索パラメータ
6. 検索条件の評価規則
7. 会議単位簡易出力API
8. 会議単位出力API
9. 発言単位出力API
10. ページング
11. ソート順
12. エラー仕様
13. HTTP仕様
14. APIと内部データモデルの関係
15. 将来拡張

# 1. 目的

本APIは、地方公共団体の議会が公開する会議録を横断的に検索および取得するためのHTTP APIを提供する。

APIの基本設計は国立国会図書館「国会会議録検索システム検索用API」を参考とする。

国会会議録検索APIと同様に、検索条件は原則として共通とし、利用目的に応じて次の3種類の出力形式を提供する。

* 会議単位簡易出力
* 会議単位出力
* 発言単位出力

地方議会固有の検索条件として、自治体、自治体コードおよび都道府県を追加する。

# 2. 設計方針

## 2.1 国会会議録APIとの類似性

本APIでは、国会会議録API利用者が理解しやすいよう、可能な範囲で以下を踏襲する。

* HTTP GETによる検索
* `meeting_list`、`meeting`、`speech`の3種類
* `startRecord`による開始位置指定
* `maximumRecords`による件数指定
* `any`による発言本文検索
* `speaker`による発言者検索
* `nameOfMeeting`による会議名検索
* `from`および`until`による開催日検索
* `speechNumber`による発言番号検索
* `speakerPosition`による肩書き検索
* `speakerGroup`による会派検索
* `speechID`による発言の一意検索
* 開催日の新しい順を標準ソート順とする

国会会議録APIでは、`any`に複数語を指定した場合はAND検索、`nameOfMeeting`および`speaker`ではOR検索となる。本APIでもこの規則を踏襲する。

## 2.2 地方議会向け変更

国会固有の以下の概念は採用しない。

* 院名
* 国会回次
* 国会号数
* 追録・附録
* 目次・索引
* 議事冒頭・本文区分

代わりに以下を導入する。

* 都道府県
* 自治体
* 全国地方公共団体コード
* 会期・定例会等を表すsession
* 地方議会固有の会議名

# 3. 基本仕様

ベースパスは次のとおりとする。

```text
/api
```

文字コードはUTF-8とする。

応答形式はJSONのみとする。

検索リクエストにはHTTP GETを使用する。

例:

```http
GET /api/speech?any=学校給食&municipalityCode=341002
```

# 4. API一覧

## 4.1 会議単位簡易出力

```http
GET /api/meeting_list
```

検索条件に一致した会議のメタデータを返却する。

発言本文は返却しない。

発言条件によって会議がヒットした場合は、一致した発言の最低限の情報を含めることができる。

## 4.2 会議単位出力

```http
GET /api/meeting
```

検索条件に一致した会議と、当該会議に含まれるすべての発言を返却する。

## 4.3 発言単位出力

```http
GET /api/speech
```

検索条件に一致した発言のみを返却する。

各発言には、それが属する会議および自治体の情報を付与する。

# 5. 共通検索パラメータ

| パラメータ              | 型       | 検索方法 | 説明            |
| ------------------ | ------- | ---- | ------------- |
| `startRecord`      | integer | -    | 取得開始位置        |
| `maximumRecords`   | integer | -    | 最大取得件数        |
| `prefecture`       | string  | 部分一致 | 都道府県名         |
| `municipality`     | string  | 部分一致 | 自治体名          |
| `municipalityCode` | string  | 完全一致 | 全国地方公共団体コード   |
| `nameOfMeeting`    | string  | 部分一致 | 本会議・委員会等の会議名  |
| `session`          | string  | 部分一致 | 定例会・臨時会等の会期名称 |
| `any`              | string  | 部分一致 | 発言本文          |
| `speaker`          | string  | 部分一致 | 発言者名          |
| `from`             | date    | 範囲   | 開催日下限         |
| `until`            | date    | 範囲   | 開催日上限         |
| `speechNumber`     | integer | 完全一致 | 会議内の発言番号      |
| `speakerPosition`  | string  | 部分一致 | 発言者肩書き        |
| `speakerGroup`     | string  | 部分一致 | 会派等           |
| `speakerRole`      | string  | 部分一致 | 発言者役割         |
| `speechID`         | string  | 完全一致 | 発言ID          |
| `meetingID`        | string  | 完全一致 | 会議ID          |

少なくとも1つの実質的検索条件を指定しなければならない。

`startRecord`および`maximumRecords`のみを指定したリクエストは検索条件とはみなさない。

# 6. 検索条件の評価規則

## 6.1 パラメータ間

異なる検索パラメータはAND条件として評価する。

例:

```text
municipality=広島市
any=学校給食
speaker=山田
```

は、

```text
自治体名に「広島市」を含む
AND
発言本文に「学校給食」を含む
AND
発言者名に「山田」を含む
```

を意味する。

## 6.2 any

半角スペース区切りで複数語を指定した場合はAND検索とする。

```text
any=学校給食 無償化
```

は、

```text
speech LIKE '%学校給食%'
AND
speech LIKE '%無償化%'
```

相当とする。

## 6.3 speaker

半角スペース区切りで複数語を指定した場合はOR検索とする。

```text
speaker=田中 鈴木
```

は、

```text
speaker LIKE '%田中%'
OR
speaker LIKE '%鈴木%'
```

相当とする。

## 6.4 nameOfMeeting

半角スペース区切りで複数語を指定した場合はOR検索とする。

```text
nameOfMeeting=総務 文教
```

は、「総務」または「文教」を含む会議を対象とする。

## 6.5 その他の部分一致項目

`municipality`、`prefecture`、`session`、`speakerPosition`、`speakerGroup`および`speakerRole`は、v0.1では入力文字列全体による部分一致とする。

複数語構文は定義しない。

## 6.6 日付

日付はISO 8601の以下の形式とする。

```text
YYYY-MM-DD
```

`from`と`until`の両方を指定した場合は両端を含む。

```text
from <= meeting.date <= until
```

特定日の検索では同じ日を指定する。

```text
from=2026-09-10
until=2026-09-10
```

# 7. 会議単位簡易出力API

## 7.1 エンドポイント

```http
GET /api/meeting_list
```

## 7.2 maximumRecords

範囲:

```text
1～100
```

デフォルト:

```text
30
```

## 7.3 レスポンス

```json
{
  "numberOfRecords": 120,
  "numberOfReturn": 30,
  "startRecord": 1,
  "nextRecordPosition": 31,
  "meetingRecord": [
    {
      "meetingID": "341002-20260910-001",
      "prefecture": "広島県",
      "municipality": "広島市",
      "municipalityCode": "341002",
      "session": "令和8年第3回定例会",
      "nameOfMeeting": "本会議",
      "date": "2026-09-10",
      "speechRecord": [
        {
          "speechID": "341002-20260910-001-0042",
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

`speechRecord`は発言に関する検索条件によってヒットした場合にのみ含めてもよい。

発言本文は含めない。

# 8. 会議単位出力API

## 8.1 エンドポイント

```http
GET /api/meeting
```

## 8.2 maximumRecords

範囲:

```text
1～10
```

デフォルト:

```text
3
```

## 8.3 レスポンス

```json
{
  "numberOfRecords": 1,
  "numberOfReturn": 1,
  "startRecord": 1,
  "nextRecordPosition": null,
  "meetingRecord": [
    {
      "meetingID": "341002-20260910-001",
      "prefecture": "広島県",
      "municipality": "広島市",
      "municipalityCode": "341002",
      "session": "令和8年第3回定例会",
      "nameOfMeeting": "本会議",
      "date": "2026-09-10",
      "speechRecord": [
        {
          "speechID": "341002-20260910-001-0001",
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

# 9. 発言単位出力API

## 9.1 エンドポイント

```http
GET /api/speech
```

## 9.2 maximumRecords

範囲:

```text
1～100
```

デフォルト:

```text
30
```

## 9.3 レスポンス

```json
{
  "numberOfRecords": 123,
  "numberOfReturn": 30,
  "startRecord": 1,
  "nextRecordPosition": 31,
  "speechRecord": [
    {
      "speechID": "341002-20260910-001-0042",
      "meetingID": "341002-20260910-001",
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

発言単位APIでは、利用者が1件のレコードだけ取得しても意味を解釈できるよう、会議情報および自治体情報を非正規化して含める。

# 10. ページング

`startRecord`は1始まりとする。

```text
startRecord=1
```

が先頭レコードを表す。

レスポンスには以下を含める。

```text
numberOfRecords
numberOfReturn
startRecord
nextRecordPosition
```

最終ページでは、

```json
"nextRecordPosition": null
```

とする。

# 11. ソート順

デフォルトソート順は次のとおりとする。

```text
meeting.date DESC
meeting.id ASC
speech.order ASC
```

すなわち、開催日の新しい会議を優先する。

同日の会議については一意かつ安定した順序となるようIDで補助ソートする。

発言単位出力では同一会議内の発言順を維持する。

# 12. エラー仕様

エラーはJSONで返却する。

基本形式:

```json
{
  "message": "Invalid request.",
  "details": [
    "maximumRecords must be between 1 and 100."
  ]
}
```

## 12.1 HTTPステータス

| 状況        |   Status |
| --------- | -------: |
| 正常        |      200 |
| パラメータ不正   |      400 |
| 該当リソースなし  | 原則200、0件 |
| サーバー内部エラー |      500 |
| 一時利用不能    |      503 |

検索結果0件はエラーとせず、

```json
{
  "numberOfRecords": 0,
  "numberOfReturn": 0,
  "startRecord": 1,
  "nextRecordPosition": null,
  "speechRecord": []
}
```

のように返却する。

# 13. HTTP仕様

レスポンスContent-Type:

```text
application/json; charset=utf-8
```

APIは読み取り専用とする。

v0.1では以下のHTTPメソッドのみ公開する。

```text
GET
```

認証は要求しない。

CORSの許可範囲は運用環境で別途定める。

# 14. APIと内部データモデルの関係

APIレスポンス形式はCanonical Data Modelそのものではない。

Canonical Data Modelを基礎として、利用目的に応じて表示粒度を変換する。

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

APIでは利便性のため、自治体情報や会議情報を発言レコードへ重複して含めることを許容する。

# 15. 将来拡張

v0.1では以下を実装対象外とする。

* XML出力
* 全文検索エンジン
* 検索結果ランキング
* 形態素解析
* 曖昧検索
* 類義語検索
* AI検索
* GraphQL
* 書き込みAPI

検索性能が不足した場合は、外部API仕様を維持したままSQLiteの検索実装をFTS等へ置き換える。

外部インターフェースと内部検索方式を分離する。
