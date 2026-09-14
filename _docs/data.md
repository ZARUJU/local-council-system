# データモデル

この文書は、会議録データをどの意味で表現し、Git / SQLite / API の各層へどう載せるかを定義します。

関連:

- システム全体の流れ → [architecture.md](architecture.md)
- 公開 ID の生成規則 → [id.md](id.md)
- HTTP API の契約 → [api.md](api.md)
- 文書の読み順と優先関係 → [README.md](README.md)

## 目次

- [目的](#目的)
- [基本原則](#基本原則)
- [Canonical Data Model](#canonical-data-model)
- [公開 ID](#公開-id)
- [Git 保存形式](#git-保存形式)
- [SQLite 格納形式](#sqlite-格納形式)
- [API との対応](#api-との対応)
- [NULL・欠損値](#null欠損値)
- [正規化規則](#正規化規則)
- [データ更新](#データ更新)

## 目的

地方議会会議録データについて次を定義する。

1. システム全体で共有する Canonical Data Model
2. Git リポジトリ上の永続保存形式
3. 検索および API 提供に利用する SQLite 格納形式
4. API 利用者へ提供するレスポンス形式との対応

Git 上の JSON をデータの正本とする。SQLite は正本ではなく、Git 上のデータから再生成可能な検索・配信用データベースとする。

## 基本原則

### Source of Truth

```text
Canonical JSON = Source of Truth
SQLite         = Derived Data
API Response   = View
```

SQLite データベースを削除しても、Git 上の Canonical JSON から完全に再構築できなければならない。

Collector、Parser および Normalizer が検索用 SQLite を直接正本として更新する設計は採用しない。収集・変換のための作業用 SQLite は許可する。作業用 SQLite は正本ではなく、API および Database Builder の入力にもならない。

### 意味の一貫性

保存形式・SQLite 形式・API 形式では構造や粒度を変えてよい。ただし、同一フィールドが表す意味を変更してはならない。

例: Canonical の `speech.id`、SQLite の `speeches.id`、API の `speechID` は同一の識別子を表す。

### 各層の責務

```text
Canonical = 意味
Git       = 永続化
SQLite    = 検索
API       = 配布
```

| 層 | 定義すること |
| --- | --- |
| Canonical Data Model | 地方議会会議録というデータをどう表現するか |
| Git 保存形式 | データをどの単位・どのファイル構成で永続保存するか |
| SQLite 格納形式 | データをどのように検索しやすく配置するか。ここでの SQLite は検索用データベースを指す。Collector の作業用 SQLite は正本でも検索用 DB でもない |
| API レスポンス形式 | 外部利用者にどの粒度でデータを提供するか |

各層は同一の事実を表すが、それぞれの用途に応じてデータの粒度および重複度を変更する。

## Canonical Data Model

主要エンティティは次とする。

```text
Municipality
Meeting
Speech
Speaker
Source
```

関係:

```text
Municipality
     │
     └── Meeting
            │
            ├── Source
            └── Speech
                   └── Speaker
```

### Municipality

自治体を表す。

```text
code
name
prefecture
```

#### code

全国地方公共団体コード。型は `string`。数字として扱わず文字列とする。

#### name

自治体正式名称。

#### prefecture

都道府県名。

### Meeting

1 件の会議録を表す。

```text
id
municipalityCode
sourceIdentity
session
name
date
issue
speeches
source
```

#### id

会議を一意に識別する公開 ID。生成規則は [id.md](id.md) を参照する。

#### municipalityCode

`Municipality.code` への参照。

#### sourceIdentity

公開 ID の生成材料となった収集元識別子。公開 ID そのものではない。詳細は [id.md](id.md) を参照する。

#### session

自治体が公表する会期等の名称。取得できない場合は null を許容する。

```text
令和8年第3回定例会
令和8年第1回臨時会
```

#### name

会議名。

```text
本会議
総務委員会
文教委員会
予算特別委員会
```

#### date

開催日。形式は `YYYY-MM-DD`。

#### issue

原資料に明確な号数が存在する場合の号数。存在しない場合は null。

### Speech

1 件の発言を表す。

```text
id
order
sourceIdentity
speaker
text
startPage
sourceURL
```

#### id

発言を一意に識別する公開 ID。生成規則は [id.md](id.md) を参照する。

#### order

会議中の発言順。整数とする。原資料に明示的な発言番号が存在しない場合は、Parser が本文上の順序から採番する。

#### sourceIdentity

公開 ID の生成材料。詳細は [id.md](id.md) を参照する。

#### speaker

Speaker オブジェクト。

#### text

発言本文。原則として原資料の本文を保持する。

#### startPage

PDF 等でページ番号が取得可能な場合に設定する。取得できない場合は null。

#### sourceURL

発言単位の URL が存在する場合に設定する。存在しない場合は null。

### Speaker

```text
name
yomi
group
position
role
```

`name` 以外は null を許容する。

#### name

原資料上の発言者名。

#### yomi

読み仮名。

#### group

会派・所属。

#### position

肩書き。例: 市長、議員、教育長、議長、副市長。

#### role

その他の発言上の役割。例: 参考人、公述人、説明員。

### Source

原典情報を保持する。

```text
url
pdfURL
```

Canonical JSON は原資料の所在を保持する。HTML や PDF のバイト列そのものは v0.1 では正本へ保存しない。

必要に応じて将来次を追加可能とする。

```text
provider
documentID
retrievedAt
contentHash
```

ただし、取得のたびに値が変わるメタデータを各 Canonical JSON へ無条件に書き込み、Git 差分を発生させることは避ける。

## 公開 ID

公開 ID は収集元の URL や DB 内部の連番に依存しない、決定論的な UUIDv5 とする。

生成規則、フォールバック、変更してよい場合／いけない場合は [id.md](id.md) が定義する。本文書では Canonical 上のフィールド名と、他形式への対応だけを扱う。

- Canonical: `meeting.id` / `speech.id`
- SQLite: `meetings.id` / `speeches.id`（公開 ID を TEXT で保持する。内部整数主キーを別に持つ場合は [id.md](id.md) を参照）
- API: `meetingID` / `speechID`

ID は一度公開した後、原則として変更しない。

## Git 保存形式

原則として 1 ファイル = 1 会議 とする。

理由:

- 1 会議内の発言を自然な単位でまとめられる
- 自治体情報や会議情報の重複を減らせる
- Git diff を会議単位で確認できる
- Parser の再実行結果を比較しやすい
- 1 発言 1 ファイルよりファイル数を抑えられる

ファイルパスは Git 上の配置であり、公開 ID そのものではない。公開 ID は UUIDv5 であり、ファイル名から一意に復元する必要はない。一方、同一会議を常に同じパスへ書くため、パスは自治体・開催日・同日内の識別番号から決定論的に決める。

### ディレクトリ構成

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

| 階層 | 内容 |
| --- | --- |
| 第 1 階層 | 都道府県コード |
| 第 2 階層 | 全国地方公共団体コード |
| 第 3 階層 | 西暦年 |
| ファイル名 | `YYYY-MM-DD-NNN.json` |

### JSON ファイル仕様

Municipality の名称および都道府県名は原則として各会議ファイルに重複保存しない。`municipalityCode` から `master/municipalities.json` を参照する。

```json
{
  "schemaVersion": "1.0",
  "meeting": {
    "id": "9f55c8d4-73e4-5e17-a5b7-8c4d12e8d311",
    "municipalityCode": "341002",
    "sourceIdentity": {
      "system": "voices",
      "meetingId": "20260910001"
    },
    "session": "令和8年第3回定例会",
    "name": "本会議",
    "date": "2026-09-10",
    "issue": null
  },
  "speeches": [
    {
      "id": "b1c2d3e4-f5a6-5789-8bcd-ef0123456789",
      "order": 1,
      "sourceIdentity": {
        "speechId": "10001"
      },
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

### Git 運用上の規則

JSON は次を満たすものとする。

- UTF-8
- BOM なし
- LF 改行
- 末尾改行あり
- 整形済み JSON
- インデント幅を固定
- キー順を固定
- 不必要なタイムスタンプを生成しない

同じ入力データに対して Parser を再実行した場合、意味上の変更がなければ同一 JSON が生成されることを目標とする。出力は可能な限り決定論的でなければならない。

### Schema Version

各会議 JSON のルートに `"schemaVersion": "1.0"` を持つ。

Semantic Versioning に準じ、少なくとも `1.0` / `1.1` / `2.0` の考え方を用いる。後方互換性を失う変更では Major Version を更新する（例: `1.x` → `2.0`）。フィールドの追加など後方互換な変更では Minor Version を更新できる。

## SQLite 格納形式

SQLite は検索効率を優先する。Canonical JSON と完全に同一の構造を維持する必要はない。

```text
municipalities
meetings
speeches
```

Speaker 専用テーブルは v0.1 では作成しない。人物同定を行わず「その発言時点に記録された発言者情報」を Speech の属性として扱うためである。

v0.1 では発言本文検索を通常の `LIKE` で実装する。全文検索エンジンまたは FTS5 は必須としない。

```sql
SELECT *
FROM speeches
WHERE speech_text LIKE '%' || :keyword || '%';
```

### municipalities

```sql
CREATE TABLE municipalities (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    prefecture TEXT NOT NULL
);
```

### meetings

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

`meetings.id` には Canonical の公開 ID（UUIDv5）を格納する。SQLite 内部の整数主キーを別に持つことは禁止しない。その場合の推奨は [id.md](id.md) を参照する。

### speeches

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

## API との対応

API レスポンス形式の契約は [api.md](api.md) が定義する。本節は Canonical / SQLite / API のフィールド対応のみを扱う。

API では Canonical Model を利用目的に応じて非正規化する。Canonical JSON では `Meeting → Speech[]` だが、発言単位 API では Speech に Meeting と Municipality を付けて 1 レコードとして返す。自治体情報や会議情報を発言レコードへ重複して含めることを許容する。

| Canonical | SQLite | API |
| --- | --- | --- |
| `meeting.id` | `meetings.id` | `meetingID` |
| `meeting.municipalityCode` | `meetings.municipality_code` | `municipalityCode` |
| `meeting.session` | `meetings.session` | `session` |
| `meeting.name` | `meetings.name` | `nameOfMeeting` |
| `meeting.date` | `meetings.date` | `date` |
| `speech.id` | `speeches.id` | `speechID` |
| `speech.order` | `speeches.speech_order` | `speechOrder` |
| `speech.speaker.name` | `speeches.speaker_name` | `speaker` |
| `speech.speaker.yomi` | `speeches.speaker_yomi` | `speakerYomi` |
| `speech.speaker.group` | `speeches.speaker_group` | `speakerGroup` |
| `speech.speaker.position` | `speeches.speaker_position` | `speakerPosition` |
| `speech.speaker.role` | `speeches.speaker_role` | `speakerRole` |
| `speech.text` | `speeches.speech_text` | `speech` |
| `speech.startPage` | `speeches.start_page` | `startPage` |
| `speech.sourceURL` | `speeches.source_url` | `speechURL` |
| `source.url` | `meetings.source_url` | `meetingURL` |
| `source.pdfURL` | `meetings.pdf_url` | `pdfURL` |

API の `prefecture` および `municipality` は、SQLite 上で `municipalities` を JOIN して生成する。`sourceIdentity` は原則として通常の検索 API レスポンスには含めない。

## NULL・欠損値

収集元に項目が存在しない場合は、推測値を作成せず `null` とする。空文字列による欠損表現は使用しない。

悪い例: `"speakerPosition": ""`

良い例: `"speakerPosition": null`

ただし、本文そのものが空であることが原典上意味を持つ特殊ケースについては別途 Parser 仕様で定義する。

## 正規化規則

原則として原資料に存在する情報を保持する。過度な文字列正規化を行わない。

特に発言本文については、検索の都合で原文を書き換えない。検索用に正規化文字列が必要になった場合は、Canonical 値とは別の派生値として SQLite 側で生成する。

```text
Canonical: 山田　太郎
Derived:   山田太郎
```

Canonical 値を書き換えてはならない。

## データ更新

収集システムは既存会議を再取得した場合、Canonical JSON を再生成して既存ファイルとの差分を判定する。

```text
Web → Parse → Canonical JSON → git diff
```

内容に変更がなければファイルを書き換えない。内容に変更が存在する場合のみ Git 上の差分として記録する。

SQLite については Git データ更新後に再ロードする。v0.1 の運用は Canonical JSON からの全再構築を標準とする（[architecture.md](architecture.md)）。スキーマとローダは、将来 `incremental load` と `rebuild database` の両方を実装できる構造とする。
