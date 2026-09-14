# 地方議会会議録データ仕様書

## 目次

1. 目的
2. 基本原則
3. データフロー
4. Canonical Data Model
5. ID仕様
6. Git保存形式
7. ディレクトリ構成
8. JSONファイル仕様
9. SQLite格納形式
10. SQLiteテーブル定義
11. APIレスポンス形式
12. 各形式間のマッピング
13. NULL・欠損値
14. 正規化規則
15. Git運用上の規則
16. Schema Version
17. データ更新
18. 設計上の責務

# 1. 目的

本仕様書は、地方議会会議録データについて以下を定義する。

1. システム全体で共有するCanonical Data Model
2. Gitリポジトリ上の永続保存形式
3. 検索およびAPI提供に利用するSQLite格納形式
4. API利用者へ提供するレスポンス形式

Git上のJSONをデータの正本とする。

SQLiteは正本ではなく、Git上のデータから再生成可能な検索・配信用データベースとする。

# 2. 基本原則

## 2.1 Source of Truth

データの正本はGitリポジトリに保存されたCanonical JSONとする。

```text
Canonical JSON = Source of Truth
```

SQLiteは派生データとする。

```text
SQLite = Derived Data
```

APIレスポンスも派生データとする。

```text
API Response = View
```

## 2.2 再生成可能性

SQLiteデータベースを削除しても、Git上のCanonical JSONから完全に再構築できなければならない。

## 2.3 意味の一貫性

保存形式・SQLite形式・API形式では構造や粒度を変えてよい。

ただし、同一フィールドが表す意味を変更してはならない。

例:

```text
Canonical speech.id
SQLite speeches.id
API speechID
```

は同一の識別子を表す。

# 3. データフロー

```text
地方議会Webサイト
       ↓
   Collector
       ↓
     Parser
       ↓
   Normalizer
       ↓
    Validator
       ↓
Canonical JSON
       ↓
      Git
       ↓
     Loader
       ↓
     SQLite
       ↓
       API
```

Collector、ParserおよびNormalizerがSQLiteを直接正本として更新する設計は採用しない。

# 4. Canonical Data Model

主要エンティティは以下とする。

```text
Municipality
Meeting
Speech
Speaker
Source
```

関係は次のとおり。

```text
Municipality
     │
     └── Meeting
            │
            └── Speech
                   │
                   └── Speaker
```

MeetingはSource情報を持つ。

# 4.1 Municipality

自治体を表す。

```text
code
name
prefecture
```

### code

全国地方公共団体コード。

型:

```text
string
```

数字として扱わず文字列とする。

### name

自治体正式名称。

### prefecture

都道府県名。

# 4.2 Meeting

1件の会議録を表す。

推奨フィールド:

```text
id
municipalityCode
session
name
date
issue
speeches
source
```

### id

会議を一意に識別するID。

### municipalityCode

Municipality.codeへの参照。

### session

自治体が公表する会期等の名称。

例:

```text
令和8年第3回定例会
令和8年第1回臨時会
```

取得できない場合はnullを許容する。

### name

会議名。

例:

```text
本会議
総務委員会
文教委員会
予算特別委員会
```

### date

開催日。

形式:

```text
YYYY-MM-DD
```

### issue

原資料に明確な号数が存在する場合の号数。

存在しない場合はnull。

# 4.3 Speech

1件の発言を表す。

推奨フィールド:

```text
id
order
speaker
text
startPage
sourceURL
```

### id

発言を一意に識別するID。

### order

会議中の発言順。

整数とする。

原資料に明示的な発言番号が存在しない場合は、Parserが本文上の順序から採番する。

### speaker

Speakerオブジェクト。

### text

発言本文。

原則として原資料の本文を保持する。

### startPage

PDF等でページ番号が取得可能な場合に設定する。

取得できない場合はnull。

### sourceURL

発言単位のURLが存在する場合に設定する。

存在しない場合はnull。

# 4.4 Speaker

```text
name
yomi
group
position
role
```

すべての項目について、`name`以外はnullを許容する。

### name

原資料上の発言者名。

### yomi

読み仮名。

### group

会派・所属。

### position

肩書き。

例:

```text
市長
議員
教育長
議長
副市長
```

### role

その他の発言上の役割。

例:

```text
参考人
公述人
説明員
```

# 4.5 Source

原典情報を保持する。

```text
url
pdfURL
```

必要に応じて将来以下を追加可能とする。

```text
provider
documentID
retrievedAt
contentHash
```

ただし、取得のたびに値が変わるメタデータを各Canonical JSONへ無条件に書き込み、Git差分を発生させることは避ける。

# 5. ID仕様

IDは収集元のURLやDB内部の連番に依存しない安定した値とする。

v0.1では以下を推奨形式とする。

## 5.1 Meeting ID

```text
{municipalityCode}-{date}-{sequence}
```

例:

```text
341002-20260910-001
```

`sequence`は同一自治体・同一開催日に複数会議が存在する場合の識別番号とする。

3桁のゼロ埋めとする。

## 5.2 Speech ID

```text
{meetingID}-{speechOrder}
```

例:

```text
341002-20260910-001-0042
```

`speechOrder`は4桁ゼロ埋めとする。

IDは一度公開した後、原則として変更しない。

# 6. Git保存形式

原則として、

```text
1ファイル = 1会議
```

とする。

理由は以下のとおり。

* 1会議内の発言を自然な単位でまとめられる
* 自治体情報や会議情報の重複を減らせる
* Git diffを会議単位で確認できる
* Parserの再実行結果を比較しやすい
* 1発言1ファイルよりファイル数を抑えられる

# 7. ディレクトリ構成

推奨構成:

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
    └── 34/
        └── 341002/
            └── 2026/
                ├── 2026-09-10-001.json
                └── 2026-09-10-002.json
```

第1階層:

```text
都道府県コード
```

第2階層:

```text
全国地方公共団体コード
```

第3階層:

```text
西暦年
```

ファイル名:

```text
YYYY-MM-DD-NNN.json
```

とする。

Meeting IDとファイルパスの対応を可能な限り決定論的にする。

# 8. JSONファイル仕様

例:

```json
{
  "schemaVersion": "1.0",
  "meeting": {
    "id": "341002-20260910-001",
    "municipalityCode": "341002",
    "session": "令和8年第3回定例会",
    "name": "本会議",
    "date": "2026-09-10",
    "issue": null
  },
  "speeches": [
    {
      "id": "341002-20260910-001-0001",
      "order": 1,
      "speaker": {
        "name": "山田太郎",
        "yomi": null,
        "group": "○○会",
        "position": "議員",
        "role": null
      },
      "text": "学校給食について質問します。",
      "startPage": null,
      "sourceURL": null
    }
  ],
  "source": {
    "url": "https://example.jp/meeting/123",
    "pdfURL": null
  }
}
```

Municipalityの名称および都道府県名は原則として各会議ファイルに重複保存しない。

`municipalityCode`から`master/municipalities.json`を参照する。

# 9. SQLite格納形式

SQLiteは検索効率を優先する。

Canonical JSONと完全に同一の構造を維持する必要はない。

以下のように正規化する。

```text
municipalities
meetings
speeches
```

Speaker専用テーブルはv0.1では作成しない。

理由は、人物同定を行わず「その発言時点に記録された発言者情報」をSpeechの属性として扱うためである。

# 10. SQLiteテーブル定義

## 10.1 municipalities

```sql
CREATE TABLE municipalities (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prefecture TEXT NOT NULL
);
```

## 10.2 meetings

```sql
CREATE TABLE meetings (
    id TEXT PRIMARY KEY,
    municipality_code TEXT NOT NULL,
    session TEXT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    issue INTEGER,
    source_url TEXT NOT NULL,
    pdf_url TEXT,

    FOREIGN KEY (
        municipality_code
    ) REFERENCES municipalities(code)
);
```

推奨インデックス:

```sql
CREATE INDEX idx_meetings_date
ON meetings(date);

CREATE INDEX idx_meetings_municipality
ON meetings(municipality_code);

CREATE INDEX idx_meetings_name
ON meetings(name);
```

## 10.3 speeches

```sql
CREATE TABLE speeches (
    id TEXT PRIMARY KEY,
    meeting_id TEXT NOT NULL,
    speech_order INTEGER NOT NULL,

    speaker_name TEXT NOT NULL,
    speaker_yomi TEXT,
    speaker_group TEXT,
    speaker_position TEXT,
    speaker_role TEXT,

    speech_text TEXT NOT NULL,

    start_page INTEGER,
    source_url TEXT,

    FOREIGN KEY (
        meeting_id
    ) REFERENCES meetings(id),

    UNIQUE (
        meeting_id,
        speech_order
    )
);
```

推奨インデックス:

```sql
CREATE INDEX idx_speeches_meeting
ON speeches(meeting_id);

CREATE INDEX idx_speeches_speaker
ON speeches(speaker_name);
```

v0.1では発言本文検索を通常の`LIKE`で実装する。

例:

```sql
SELECT *
FROM speeches
WHERE speech_text LIKE '%' || :keyword || '%';
```

全文検索エンジンまたはFTS5は必須としない。

# 11. APIレスポンス形式

APIではCanonical Modelを利用目的に応じて非正規化する。

例えばCanonical JSONでは、

```text
Meeting
  └── Speech[]
```

となっているが、発言単位APIでは、

```text
Speech
+ Meeting
+ Municipality
```

を1レコードとして返す。

例:

```json
{
  "speechID": "341002-20260910-001-0001",
  "meetingID": "341002-20260910-001",

  "prefecture": "広島県",
  "municipality": "広島市",
  "municipalityCode": "341002",

  "session": "令和8年第3回定例会",
  "nameOfMeeting": "本会議",
  "date": "2026-09-10",

  "speechOrder": 1,

  "speaker": "山田太郎",
  "speakerYomi": null,
  "speakerGroup": "○○会",
  "speakerPosition": "議員",
  "speakerRole": null,

  "speech": "学校給食について質問します。",

  "startPage": null,
  "speechURL": null,

  "meetingURL": "https://example.jp/meeting/123",
  "pdfURL": null
}
```

# 12. 各形式間のマッピング

| Canonical                  | SQLite                       | API                |
| -------------------------- | ---------------------------- | ------------------ |
| `meeting.id`               | `meetings.id`                | `meetingID`        |
| `meeting.municipalityCode` | `meetings.municipality_code` | `municipalityCode` |
| `meeting.session`          | `meetings.session`           | `session`          |
| `meeting.name`             | `meetings.name`              | `nameOfMeeting`    |
| `meeting.date`             | `meetings.date`              | `date`             |
| `speech.id`                | `speeches.id`                | `speechID`         |
| `speech.order`             | `speeches.speech_order`      | `speechOrder`      |
| `speech.speaker.name`      | `speeches.speaker_name`      | `speaker`          |
| `speech.speaker.yomi`      | `speeches.speaker_yomi`      | `speakerYomi`      |
| `speech.speaker.group`     | `speeches.speaker_group`     | `speakerGroup`     |
| `speech.speaker.position`  | `speeches.speaker_position`  | `speakerPosition`  |
| `speech.speaker.role`      | `speeches.speaker_role`      | `speakerRole`      |
| `speech.text`              | `speeches.speech_text`       | `speech`           |
| `speech.startPage`         | `speeches.start_page`        | `startPage`        |
| `speech.sourceURL`         | `speeches.source_url`        | `speechURL`        |
| `source.url`               | `meetings.source_url`        | `meetingURL`       |
| `source.pdfURL`            | `meetings.pdf_url`           | `pdfURL`           |

APIの、

```text
prefecture
municipality
```

は、SQLite上で`municipalities`をJOINして生成する。

# 13. NULL・欠損値

収集元に項目が存在しない場合は、推測値を作成せず`null`とする。

例えば、

```json
{
  "speaker": {
    "name": "山田太郎",
    "yomi": null,
    "group": null,
    "position": null,
    "role": null
  }
}
```

とする。

空文字列による欠損表現は使用しない。

悪い例:

```json
"speakerPosition": ""
```

良い例:

```json
"speakerPosition": null
```

ただし、本文そのものが空であることが原典上意味を持つ特殊ケースについては別途Parser仕様で定義する。

# 14. 正規化規則

原則として原資料に存在する情報を保持する。

過度な文字列正規化を行わない。

特に発言本文については、検索の都合で原文を書き換えない。

検索用に正規化文字列が必要になった場合は、Canonical値とは別の派生値としてSQLite側で生成する。

例えば、

```text
Canonical:
山田　太郎

Derived:
山田太郎
```

のように扱う。

Canonical値を書き換えてはならない。

# 15. Git運用上の規則

JSONは以下を満たすものとする。

* UTF-8
* BOMなし
* LF改行
* 末尾改行あり
* 整形済みJSON
* インデント幅を固定
* キー順を固定
* 不必要なタイムスタンプを生成しない

同じ入力データに対してParserを再実行した場合、意味上の変更がなければ同一JSONが生成されることを目標とする。

すなわち、出力は可能な限り決定論的でなければならない。

# 16. Schema Version

各会議JSONのルートに、

```json
"schemaVersion": "1.0"
```

を持つ。

Semantic Versioningに準じ、少なくとも次の考え方を用いる。

```text
1.0
1.1
2.0
```

後方互換性を失う変更ではMajor Versionを更新する。

例:

```text
1.x → 2.0
```

フィールドの追加など後方互換な変更ではMinor Versionを更新できる。

# 17. データ更新

収集システムは既存会議を再取得した場合、Canonical JSONを再生成して既存ファイルとの差分を判定する。

```text
Web
 ↓
Parse
 ↓
Canonical JSON
 ↓
git diff
```

内容に変更がなければファイルを書き換えない。

内容に変更が存在する場合のみGit上の差分として記録する。

SQLiteについてはGitデータ更新後に再ロードする。

MVPでは差分更新と全再構築の両方を許容する。

```text
incremental load
```

および、

```text
rebuild database
```

を実装可能な構造とする。

# 18. 設計上の責務

各層の責務は以下とする。

## Canonical Data Model

「地方議会会議録というデータをどう表現するか」を定義する。

## Git保存形式

「データをどの単位・どのファイル構成で永続保存するか」を定義する。

## SQLite格納形式

「データをどのように検索しやすく配置するか」を定義する。

## APIレスポンス形式

「外部利用者にどの粒度でデータを提供するか」を定義する。

したがって、

```text
Canonical
    = 意味

Git
    = 永続化

SQLite
    = 検索

API
    = 配布
```

という責務分担とする。

各層は同一の事実を表すが、それぞれの用途に応じてデータの粒度および重複度を変更する。
