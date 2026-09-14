# 地方議会会議録 公開ID仕様書

## 目次

1. 目的
2. 適用範囲
3. 基本方針
4. IDの種類
5. UUID仕様
6. Meeting ID
7. Speech ID
8. sourceIdentity
9. ID生成規則
10. フォールバック規則
11. IDを変更してはならない場合
12. IDを変更する場合
13. SQLite上での扱い
14. Canonical JSON上での扱い
15. API上での扱い
16. 実装例
17. 禁止事項
18. 将来互換性

# 1. 目的

本仕様書は、地方議会会議録データにおける公開用識別子の生成規則および管理方法を定義する。

公開用識別子は、以下の要件を満たさなければならない。

* 同一データに対して決定論的に同じIDを生成できる
* 異なる会議および発言間で衝突しない
* Git上のCanonical DataとAPIで共通利用できる
* SQLiteの再構築によって変更されない
* 会議名、開催日等の属性訂正によって原則として変更されない
* 収集処理を再実行しても同一IDを生成できる

# 2. 適用範囲

本仕様は以下の公開用IDに適用する。

```text
Meeting ID
Speech ID
```

SQLite内部で使用する数値主キーには適用しない。

# 3. 基本方針

公開用IDにはUUID version 5を使用する。

UUIDv5は、

```text
namespace UUID
+
name
```

からSHA-1を用いて決定論的に生成されるUUIDである。

同一namespaceと同一nameからは常に同一UUIDが生成される。

公開用IDはランダム生成してはならない。

したがって、UUIDv4は公開用IDには使用しない。

# 4. IDの種類

システムでは以下の識別子を区別する。

## 4.1 SQLite内部ID

SQLite内部でJOIN等に利用するID。

例:

```text
123
456
789
```

SQLiteの、

```sql
INTEGER PRIMARY KEY
```

を利用する。

SQLite再構築によって値が変更されてもよい。

## 4.2 公開用ID

Git上のCanonical DataおよびAPIで使用する。

例:

```text
9f55c8d4-73e4-5e17-a5b7-xxxxxxxxxxxx
```

公開後は原則として変更しない。

## 4.3 収集元ID

地方議会会議録システム等が内部的に使用している識別子。

例:

```text
12345
20260910001
kaigi_9876
```

公開用UUIDの生成材料として使用する。

# 5. UUID仕様

公開IDはRFC 9562に基づくUUID Version 5形式を使用する。

文字列表現は以下の形式とする。

```text
xxxxxxxx-xxxx-5xxx-xxxx-xxxxxxxxxxxx
```

小文字英数字を使用する。

例:

```text
9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311
```

UUIDを波括弧で囲まない。

悪い例:

```text
{9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311}
```

良い例:

```text
9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311
```

# 6. Meeting ID

Meeting IDは会議を一意に識別する。

生成規則:

```text
UUIDv5(
    MEETING_NAMESPACE,
    meetingIdentity
)
```

`meetingIdentity`は原則として以下の形式とする。

```text
{municipalityCode}:{sourceSystem}:{sourceMeetingId}
```

例:

```text
341002:voices:20260910001
```

この文字列からUUIDv5を生成する。

## 6.1 municipalityCode

全国地方公共団体コードを使用する。

例:

```text
341002
```

型は文字列とする。

## 6.2 sourceSystem

会議録を提供するシステムまたはAdapterを識別する安定した識別子とする。

例:

```text
voices
discussnet
dbsearch
static-html
pdf
custom
```

表示名称ではなく機械可読な固定識別子を使用する。

大文字小文字は区別するため、原則としてASCII小文字を使用する。

## 6.3 sourceMeetingId

収集元システムが会議を識別するために使用しているIDを使用する。

例えばURLが、

```text
https://example.jp/voices/cgi/voiweb.exe?ACT=200&KENSAKU=1&DATA=12345
```

であり、`12345`が当該システム内で会議を一意に識別している場合、

```text
sourceMeetingId = "12345"
```

とする。

# 7. Speech ID

Speech IDは発言を一意に識別する。

原則としてMeeting IDをnamespaceとしてUUIDv5を生成する。

生成規則:

```text
UUIDv5(
    meetingID,
    speechIdentity
)
```

## 7.1 収集元発言IDが存在する場合

収集元に発言固有IDが存在する場合は、それを優先する。

`speechIdentity`:

```text
source:{sourceSpeechId}
```

例:

```text
source:56789
```

したがって、

```text
UUIDv5(
    meetingID,
    "source:56789"
)
```

とする。

## 7.2 原典発言番号が存在する場合

収集元にシステム上の発言IDが存在しないが、原資料に明示的かつ安定した発言番号が存在する場合は、その番号を使用する。

```text
number:{speechNumber}
```

例:

```text
number:42
```

## 7.3 発言IDも発言番号も存在しない場合

会議内の発言順を使用する。

```text
order:{speechOrder}
```

例:

```text
order:42
```

ただし、この方式は他の方式より安定性が低い。

途中に新しい発言が発見された場合、それ以降の`speechOrder`が変化する可能性があるためである。

そのためSpeech Identityの優先順位は次のとおりとする。

```text
1. sourceSpeechId
2. 原典上の安定したspeechNumber
3. speechOrder
```

# 8. sourceIdentity

Canonical Dataには、公開用UUIDとは別に、可能な限りID生成元となった情報を保持する。

Meetingの例:

```json
{
  "id": "9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311",
  "sourceIdentity": {
    "system": "voices",
    "meetingId": "20260910001"
  }
}
```

Speechの例:

```json
{
  "id": "e5f1f604-cd64-5ac4-a6f4-xxxxxxxxxxxx",
  "sourceIdentity": {
    "speechId": "56789"
  }
}
```

収集元発言IDが存在しない場合は、

```json
{
  "sourceIdentity": {
    "speechId": null
  }
}
```

としてよい。

`sourceIdentity`はIDの由来を追跡するためのメタデータであり、公開IDそのものとは区別する。

# 9. ID生成規則

Meeting IDの生成処理は、以下の手順で行う。

```text
1. municipalityCodeを決定
2. sourceSystemを決定
3. sourceMeetingIdを取得
4. meetingIdentityを組み立て
5. MEETING_NAMESPACEを使用してUUIDv5生成
```

例:

```text
municipalityCode:
341002

sourceSystem:
voices

sourceMeetingId:
20260910001
```

から、

```text
341002:voices:20260910001
```

を生成する。

その後、

```text
UUIDv5(
    MEETING_NAMESPACE,
    "341002:voices:20260910001"
)
```

を実行する。

Speech IDについては、

```text
1. Meeting IDを取得
2. sourceSpeechIdの有無を確認
3. なければ原典上の発言番号を確認
4. それもなければspeechOrderを使用
5. Meeting IDをnamespaceとしてUUIDv5生成
```

とする。

# 10. フォールバック規則

収集元に安定した`sourceMeetingId`が存在しない場合のみ、フォールバックIDを生成する。

優先順位は以下とする。

```text
1. 収集元固有のMeeting ID
2. 収集元固有のDocument ID
3. URL内の安定した識別パラメータ
4. 正規化済み原典URL
5. 複数属性から構成したFallback Identity
```

## 10.1 URL内ID

例えば、

```text
https://example.jp/meeting?id=12345
```

の場合、

```text
12345
```

を利用できる場合はURL全体ではなくID部分を優先する。

## 10.2 URLを利用する場合

URLしか識別材料がない場合は、正規化したURLを使用する。

例えば以下を除外することを検討する。

```text
utm_source
utm_medium
session
timestamp
```

一方、会議識別に必要なクエリパラメータは除外してはならない。

URL正規化規則はAdapter単位で定義してよい。

## 10.3 属性ベースFallback

URLも安定していない場合のみ、

```text
{municipalityCode}:{date}:{session}:{meetingName}:{sequence}
```

等を用いる。

ただし、開催日、会議名、会期名等は後日訂正される可能性がある。

この方式は最後の手段として扱う。

# 11. IDを変更してはならない場合

以下の属性変更では、原則として公開IDを変更しない。

Meetingについて:

```text
会議名の修正
開催日の訂正
sessionの修正
PDF URLの変更
Web URLの変更
自治体名称の変更
Parserの変更
```

Speechについて:

```text
発言本文の訂正
発言者表記の修正
発言者肩書きの修正
会派情報の修正
ページ番号の修正
```

同一の実体である限り、IDを維持する。

# 12. IDを変更する場合

以下の場合は別IDとして扱う。

## 12.1 Meeting

実際には別の会議であることが判明した場合。

例:

```text
誤って2会議を1会議として扱っていた
```

この場合、分割後の各Meetingへ別IDを付与する。

## 12.2 Speech

実際には別発言であることが判明した場合。

例:

```text
2人の発言を誤って1件に結合していた
```

分割後の発言には別IDを付与する。

一方、単なる本文訂正ではIDを変更しない。

# 13. SQLite上での扱い

SQLite内部では公開UUIDを主キーとして利用する必要はない。

推奨構成:

```sql
CREATE TABLE meetings (
    id INTEGER PRIMARY KEY,
    public_id TEXT NOT NULL UNIQUE,
    municipality_code TEXT NOT NULL,
    session TEXT,
    name TEXT NOT NULL,
    date TEXT NOT NULL
);
```

Speech:

```sql
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

ここで、

```text
meetings.id
speeches.id
```

はSQLite内部IDである。

```text
public_id
```

がCanonical DataおよびAPIで利用する公開UUIDである。

SQLiteを再構築した場合、

```text
id
```

は変更されてもよい。

一方、

```text
public_id
```

は変更されてはならない。

# 14. Canonical JSON上での扱い

Meeting:

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
  "id": "e5f1f604-cd64-5ac4-a6f4-xxxxxxxxxxxx",
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

# 15. API上での扱い

Canonicalの、

```text
meeting.id
```

はAPI上では、

```text
meetingID
```

として返す。

Canonicalの、

```text
speech.id
```

はAPI上では、

```text
speechID
```

として返す。

例:

```json
{
  "speechID": "e5f1f604-cd64-5ac4-a6f4-xxxxxxxxxxxx",
  "meetingID": "9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311",
  "municipality": "広島市",
  "date": "2026-09-10",
  "speaker": "山田太郎",
  "speech": "学校給食について質問します。"
}
```

`sourceIdentity`は原則として通常の検索APIレスポンスには含めない。

ただし、データセット利用者向けAPI等で将来的に公開してもよい。

# 16. 実装例

Python標準ライブラリの`uuid`を使用する。

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

実際の`MEETING_NAMESPACE`には、プロジェクト専用として一度だけ生成した固定UUIDを使用する。

このnamespace UUIDはコードおよび仕様書上で固定し、後から変更してはならない。

# 17. 禁止事項

以下の方法で公開IDを生成してはならない。

## 17.1 UUIDv4

```python
uuid4()
```

収集処理を再実行するたびに異なるIDとなるため使用しない。

## 17.2 SQLite内部IDの公開

悪い例:

```json
{
  "meetingID": 1234
}
```

SQLiteを再構築すると意味が変わるため公開しない。

## 17.3 開催日のみからのID生成

悪い例:

```text
341002-20260910
```

同一日に複数会議が存在し得るため使用しない。

## 17.4 会議名のみからのID生成

悪い例:

```text
341002-honkaigi
```

複数の開催回を区別できない。

## 17.5 発言本文のハッシュのみをIDとすること

発言本文は訂正される可能性があるため使用しない。

本文修正によってIDが変化してしまう。

# 18. 将来互換性

ID生成アルゴリズムは公開後に原則変更しない。

ID生成方式を将来変更する必要が生じた場合でも、既存データのIDは維持する。

必要に応じて、

```text
identityVersion
```

等をCanonical Dataへ追加することができる。

例:

```json
{
  "identityVersion": 1
}
```

ただしv0.1では必須としない。

公開IDは外部利用者がデータ間の参照、キャッシュ、引用、分析結果の保存等に使用することを想定する。

したがって、公開済みIDの安定性をAPI仕様およびデータ仕様より優先して維持する。
