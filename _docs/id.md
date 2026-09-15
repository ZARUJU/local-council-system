# 公開 ID

この文書は、Meeting / Speech の公開用識別子の生成規則と管理方法を定義します。Canonical 上のフィールド配置と SQLite の全体スキーマは [data.md](data.md) を参照してください。

関連:

- 実装状況 → [status.md](status.md)
- Canonical / SQLite / API の対応 → [data.md](data.md)
- API 上の `meetingID` / `speechID` → `local-council-api` の api.md
- 文書の読み順と優先関係 → [README.md](README.md)

## 目次

- [目的](#目的)
- [適用範囲](#適用範囲)
- [基本方針](#基本方針)
- [ID の種類](#id-の種類)
- [UUID 仕様](#uuid-仕様)
- [Meeting ID](#meeting-id)
- [Speech ID](#speech-id)
- [sourceIdentity](#sourceidentity)
- [ID 生成手順](#id-生成手順)
- [フォールバック規則](#フォールバック規則)
- [ID を変更してはならない場合](#id-を変更してはならない場合)
- [ID を変更する場合](#id-を変更する場合)
- [各層での扱い](#各層での扱い)
- [実装例](#実装例)
- [禁止事項](#禁止事項)
- [将来互換性](#将来互換性)

## 目的

公開用識別子は、次の要件を満たさなければならない。

- 同一データに対して決定論的に同じ ID を生成できる
- 異なる会議および発言間で衝突しない
- Git 上の Canonical Data と API で共通利用できる
- SQLite の再構築によって変更されない
- 会議名、開催日等の属性訂正によって原則として変更されない
- 収集処理を再実行しても同一 ID を生成できる

## 適用範囲

本仕様は次の公開用 ID に適用する。

```text
Meeting ID
Speech ID
```

SQLite 内部で使用する数値主キーには適用しない。

## 基本方針

公開用 ID には UUID version 5 を使用する。UUIDv5 は namespace UUID と name から SHA-1 を用いて決定論的に生成される。同一 namespace と同一 name からは常に同一 UUID が生成される。

公開用 ID はランダム生成してはならない。UUIDv4 は公開用 ID には使用しない。

## ID の種類

システムでは次の識別子を区別する。

### SQLite 内部 ID

SQLite 内部で JOIN 等に利用する ID。`INTEGER PRIMARY KEY` を利用する。SQLite 再構築によって値が変更されてもよい。

内部整数主キーは必須ではない。検索用 SQLite が公開 ID を TEXT 主キーとして持つ場合のスキーマは [data.md](data.md) を参照する。

### 公開用 ID

Git 上の Canonical Data および API で使用する。

```text
9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311
```

公開後は原則として変更しない。

### 収集元 ID

地方議会会議録システム等が内部的に使用している識別子。公開用 UUID の生成材料として使用する。

```text
12345
20260910001
kaigi_9876
```

## UUID 仕様

公開 ID は RFC 9562 に基づく UUID Version 5 形式を使用する。文字列表現は次の形式とし、小文字英数字を使用する。

```text
xxxxxxxx-xxxx-5xxx-xxxx-xxxxxxxxxxxx
```

例:

```text
9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311
```

UUID を波括弧で囲まない。

悪い例: `{9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311}`

良い例: `9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311`

## Meeting ID

Meeting ID は会議を一意に識別する。

```text
UUIDv5(MEETING_NAMESPACE, meetingIdentity)
```

`meetingIdentity` は原則として次の形式とする。

```text
{municipalityCode}:{sourceSystem}:{sourceMeetingId}
```

例: `341002:voices:20260910001`

### municipalityCode

全国地方公共団体コード。型は文字列。例: `341002`

### sourceSystem

会議録を提供するシステムまたは Adapter を識別する安定した識別子とする。表示名称ではなく機械可読な固定識別子を使用する。大文字小文字は区別するため、原則として ASCII 小文字を使用する。

```text
voices
discussnet
dbsearch
static-html
pdf
custom
```

### sourceMeetingId

収集元システムが会議を識別するために使用している ID を使用する。

例えば URL が次であり、`12345` が当該システム内で会議を一意に識別している場合、`sourceMeetingId = "12345"` とする。

```text
https://example.jp/voices/cgi/voiweb.exe?ACT=200&KENSAKU=1&DATA=12345
```

## Speech ID

Speech ID は発言を一意に識別する。原則として Meeting ID を namespace として UUIDv5 を生成する。

```text
UUIDv5(meetingID, speechIdentity)
```

### 収集元発言 ID が存在する場合

収集元に発言固有 ID が存在する場合は、それを優先する。

```text
speechIdentity = source:{sourceSpeechId}
```

例: `source:56789` から `UUIDv5(meetingID, "source:56789")`

### 原典発言番号が存在する場合

収集元にシステム上の発言 ID が存在しないが、原資料に明示的かつ安定した発言番号が存在する場合は、その番号を使用する。

```text
speechIdentity = number:{speechNumber}
```

例: `number:42`

### 発言 ID も発言番号も存在しない場合

会議内の発言順を使用する。

```text
speechIdentity = order:{speechOrder}
```

例: `order:42`

この方式は他の方式より安定性が低い。途中に新しい発言が発見された場合、それ以降の `speechOrder` が変化する可能性がある。

Speech Identity の優先順位:

```text
1. sourceSpeechId
2. 原典上の安定した speechNumber
3. speechOrder
```

## sourceIdentity

Canonical Data には、公開用 UUID とは別に、可能な限り ID 生成元となった情報を保持する。`sourceIdentity` は ID の由来を追跡するためのメタデータであり、公開 ID そのものとは区別する。

Meeting:

```json
{
  "id": "9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311",
  "sourceIdentity": {
    "system": "voices",
    "meetingId": "20260910001"
  }
}
```

Speech:

```json
{
  "id": "e5f1f604-cd64-5ac4-a6f4-7b2c9d8e1a20",
  "sourceIdentity": {
    "speechId": "56789"
  }
}
```

収集元発言 ID が存在しない場合は、`"speechId": null` としてよい。

## ID 生成手順

Meeting ID:

```text
1. municipalityCode を決定
2. sourceSystem を決定
3. sourceMeetingId を取得
4. meetingIdentity を組み立て
5. MEETING_NAMESPACE を使用して UUIDv5 生成
```

例: `341002` + `voices` + `20260910001` → `341002:voices:20260910001` → `UUIDv5(MEETING_NAMESPACE, "341002:voices:20260910001")`

Speech ID:

```text
1. Meeting ID を取得
2. sourceSpeechId の有無を確認
3. なければ原典上の発言番号を確認
4. それもなければ speechOrder を使用
5. Meeting ID を namespace として UUIDv5 生成
```

## フォールバック規則

収集元に安定した `sourceMeetingId` が存在しない場合のみ、フォールバック ID を生成する。

```text
1. 収集元固有の Meeting ID
2. 収集元固有の Document ID
3. URL 内の安定した識別パラメータ
4. 正規化済み原典 URL
5. 複数属性から構成した Fallback Identity
```

### URL 内 ID

`https://example.jp/meeting?id=12345` のように、`12345` を利用できる場合は URL 全体ではなく ID 部分を優先する。

### URL を利用する場合

URL しか識別材料がない場合は、正規化した URL を使用する。例えば次を除外することを検討する。

```text
utm_source
utm_medium
session
timestamp
```

一方、会議識別に必要なクエリパラメータは除外してはならない。URL 正規化規則は Adapter 単位で定義してよい。

### 属性ベース Fallback

URL も安定していない場合のみ、次等を用いる。

```text
{municipalityCode}:{date}:{session}:{meetingName}:{sequence}
```

開催日、会議名、会期名等は後日訂正される可能性がある。この方式は最後の手段として扱う。

## ID を変更してはならない場合

以下の属性変更では、原則として公開 ID を変更しない。同一の実体である限り、ID を維持する。

Meeting:

```text
会議名の修正
開催日の訂正
session の修正
PDF URL の変更
Web URL の変更
自治体名称の変更
Parser の変更
```

Speech:

```text
発言本文の訂正
発言者表記の修正
発言者肩書きの修正
会派情報の修正
ページ番号の修正
```

## ID を変更する場合

以下の場合は別 ID として扱う。

### Meeting

実際には別の会議であることが判明した場合。例: 誤って 2 会議を 1 会議として扱っていた。分割後の各 Meeting へ別 ID を付与する。

### Speech

実際には別発言であることが判明した場合。例: 2 人の発言を誤って 1 件に結合していた。分割後の発言には別 ID を付与する。単なる本文訂正では ID を変更しない。

## 各層での扱い

### SQLite

SQLite 内部では公開 UUID を主キーとして利用する必要はない。整数主キーを使う場合の例:

```sql
CREATE TABLE meetings (
    id INTEGER PRIMARY KEY,
    public_id TEXT NOT NULL UNIQUE,
    municipality_code TEXT NOT NULL,
    session TEXT,
    name TEXT NOT NULL,
    date TEXT NOT NULL
);

CREATE TABLE speeches (
    id INTEGER PRIMARY KEY,
    public_id TEXT NOT NULL UNIQUE,
    meeting_id INTEGER NOT NULL,
    speech_order INTEGER NOT NULL,
    speech_text TEXT NOT NULL,

    FOREIGN KEY (meeting_id)
        REFERENCES meetings(id)
);
```

ここで `meetings.id` / `speeches.id` は SQLite 内部 ID、`public_id` が Canonical Data および API で利用する公開 UUID である。

SQLite を再構築した場合、内部 ID は変更されてもよい。`public_id` は変更されてはならない。

全文の検索用スキーマは [data.md](data.md) を参照する。そちらでは公開 ID を TEXT 主キーとして持つ定義を示す。どちらでも、公開 UUID が一意に保存され、API にそのまま出ることが条件である。

### Canonical JSON

```json
{
  "id": "9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311",
  "municipalityCode": "341002",
  "sourceIdentity": {
    "system": "voices",
    "meetingId": "20260910001"
  },
  "session": "令和8年第3回定例会",
  "name": "本会議",
  "date": "2026-09-10"
}
```

Speech:

```json
{
  "id": "e5f1f604-cd64-5ac4-a6f4-7b2c9d8e1a20",
  "order": 42,
  "sourceIdentity": {
    "speechId": "56789"
  },
  "speaker": {
    "name": "山田太郎",
    "position": "議員"
  },
  "text": "学校給食について質問します。"
}
```

### API

Canonical の `meeting.id` は API 上では `meetingID`、`speech.id` は `speechID` として返す。レスポンス全体の契約は `local-council-api` の api.md を参照する。

```json
{
  "speechID": "e5f1f604-cd64-5ac4-a6f4-7b2c9d8e1a20",
  "meetingID": "9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311",
  "municipality": "広島市",
  "date": "2026-09-10",
  "speaker": "山田太郎",
  "speech": "学校給食について質問します。"
}
```

`sourceIdentity` は原則として通常の検索 API レスポンスには含めない。ただし、データセット利用者向け API 等で将来的に公開してもよい。

## 実装例

Python 標準ライブラリの `uuid` を使用する。

```python
from uuid import UUID, uuid5


MEETING_NAMESPACE = UUID(
    "00000000-0000-0000-0000-000000000000"
)


def generate_meeting_id(
    municipality_code: str,
    source_system: str,
    source_meeting_id: str,
) -> UUID:
    identity = (
        f"{municipality_code}:"
        f"{source_system}:"
        f"{source_meeting_id}"
    )

    return uuid5(
        MEETING_NAMESPACE,
        identity,
    )
```

Speech:

```python
from uuid import UUID, uuid5


def generate_speech_id(
    meeting_id: UUID,
    *,
    source_speech_id: str | None,
    speech_number: int | None,
    speech_order: int,
) -> UUID:

    if source_speech_id is not None:
        identity = f"source:{source_speech_id}"

    elif speech_number is not None:
        identity = f"number:{speech_number}"

    else:
        identity = f"order:{speech_order}"

    return uuid5(
        meeting_id,
        identity,
    )
```

実際の `MEETING_NAMESPACE` には、プロジェクト専用として一度だけ生成した固定 UUID を使用する。この namespace UUID はコードおよび仕様書上で固定し、後から変更してはならない。上の nil UUID は形式の例である。

## 禁止事項

以下の方法で公開 ID を生成してはならない。

### UUIDv4

```python
uuid4()
```

収集処理を再実行するたびに異なる ID となるため使用しない。

### SQLite 内部 ID の公開

悪い例:

```json
{
  "meetingID": 1234
}
```

SQLite を再構築すると意味が変わるため公開しない。

### 開催日のみからの ID 生成

悪い例: `341002-20260910`

同一日に複数会議が存在し得るため使用しない。

### 会議名のみからの ID 生成

悪い例: `341002-honkaigi`

複数の開催回を区別できない。

### 発言本文のハッシュのみを ID とすること

発言本文は訂正される可能性があるため使用しない。本文修正によって ID が変化してしまう。

## 将来互換性

ID 生成アルゴリズムは公開後に原則変更しない。ID 生成方式を将来変更する必要が生じた場合でも、既存データの ID は維持する。

必要に応じて `identityVersion` 等を Canonical Data へ追加することができる。

```json
{
  "identityVersion": 1
}
```

ただし必須としない。いま Canonical に載せるフィールドは [status.md](status.md) と [data.md](data.md) を正とする。

公開 ID は外部利用者がデータ間の参照、キャッシュ、引用、分析結果の保存等に使用することを想定する。したがって、公開済み ID の安定性を API 仕様およびデータ仕様より優先して維持する。
