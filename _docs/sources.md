# 収集元

この文書は、対象自治体ごとの会議録公開形態、実装タイプ、収集方針を定義する。同期の時期は [ingest-sync.md](ingest-sync.md)、CLI の起動方法は [cli.md](cli.md)、プロセス境界は [architecture.md](architecture.md) を参照する。Adapter の実装状況と現在の収集範囲は [status.md](status.md) を正とする。

関連:

- 実装状況 → [status.md](status.md)
- Collector の DISCOVER / FETCH → [architecture.md](architecture.md)
- 初回同期・増分同期・lookback → [ingest-sync.md](ingest-sync.md)
- Meeting / Speech の公開 ID → [id.md](id.md)
- 文書の読み順と優先関係 → [README.md](README.md)

## 目次

- [目的](#目的)
- [実装タイプ](#実装タイプ)
- [収集してよい原資料](#収集してよい原資料)
- [対象自治体](#対象自治体)
- [広島市](#広島市)
- [広島県議会](#広島県議会)
- [Discuss](#discuss)
- [神戸市](#神戸市)
- [廿日市市](#廿日市市)
- [kensakusystem.jp](#kensakusystemjp)
- [松山市](#松山市)
- [広島県内の見送り](#広島県内の見送り)
- [自治体を追加するとき](#自治体を追加するとき)
- [ベンダー共通 Adapter](#ベンダー共通-adapter)

## 目的

Adapter は自治体ごと、収集元システムごとに置く。この文書は、その前段として次を固定する。

- その自治体の会議録が、どの公開形態か
- 本システムがそれをどの実装タイプとして扱うか
- 収集してよいか、見送るか
- Meeting Identity に使う収集元キー

調査メモ（`_ref/`）は根拠や経緯であって、実装の正ではない。収集の可否とタイプは本文書を正とする。

## 実装タイプ

公開形態を次の識別子で分類する。`source.system` は製品やサイトの識別子、実装タイプは取得手段の分類である。両者は一致しなくてよい。

| タイプ | 意味 | 収集 |
| --- | --- | --- |
| `html-cgi` | 一覧・本文が HTTP 応答の HTML（または同等の CGI）に含まれる | 可 |
| `html-search` | 公開検索の結果 HTML から会議を列挙し、本文も HTML で取れる | 可 |
| `discuss-json` | Discuss の閲覧画面が使う一覧・本文 JSON だけを POST して取る | 可 |
| `js-internal-json` | 閲覧用 HTML は殻だけで、画面専用の内部 JSON / XHR で埋まる（Discuss の閲覧 JSON 以外） | 不可 |
| `pdf` | 会議録の正が PDF | 当面不可 |

`html-cgi` と `html-search` は、ブラウザで URL を開けば会議録またはその一覧が応答本文に出る点で同じである。検索画面の有無や CGI パラメータの違いは Adapter 内に閉じる。

`discuss-json` は、議会が案内する閲覧画面（`MinuteBrowse.html` / `MinuteView.html`）が一覧と本文のために呼ぶ JSON に限る。検索・統計・ログイン・発言集作成は対象外である。詳細は [収集してよい原資料](#収集してよい原資料) を正とする。

`js-internal-json` は、利用者が画面上で読めることと、Collector が同じ内容を公開 HTTP として取得できることが一致しない。Discuss 以外の SPA には Adapter を置かない。

`pdf` は OCR やページ単位の解析が必要なため、当面は対象外とする。実装しない機能の一覧は [status.md](status.md) を正とする。

## 収集してよい原資料

Collector が FETCH してよいのは、次をすべて満たすものに限る。

- ログインなしで取得できる
- 自治体または議会が会議録の閲覧・検索用として案内している入口から辿れる
- HTTP 応答そのものに、一覧または本文が含まれる（HTML を含む）。Discuss については次項の閲覧 JSON を含む

次は FETCH しない。

- 公式の公開 API として案内されていない、画面専用の内部 JSON / JSONP / XHR（`discuss-json` で許可した閲覧 JSON を除く）
- 認証後にだけ見える会議録
- 利用規約または robots.txt が取得を禁じている経路（次の例外を除く）

例外:

- Discuss の閲覧 JSON（`POST /dnp/search/councils/index`、`minutes/get_schedule`、`minutes/get_minute`）。閲覧画面が使うものに限る。`robots.txt` は `/tenant/` を許可し、`/dnp/search/` をクローラに Disallow している。神戸市 dbsr が `Disallow: /` でも検索結果 HTML を取るのと同じく、議会が案内する会議録閲覧の経路として扱う
- dbsr の検索結果 HTML。`robots.txt` が `Disallow: /` でも、議会が案内する会議録検索の入口から辿れる一覧・本文 HTML は対象とする

画面の Network パネルで JSON が見えること、認証なしでその JSON が返ることだけでは、公開 API とはみなさない。Discuss で許可するのは、閲覧 UI が会議一覧と本文を組み立てるために呼ぶ 3 経路だけである。

DISCOVER も同様である。Discuss 以外で、初期 HTML に会議一覧が無く、内部 JSON を呼ばないと列挙できない場合は、その自治体を実装しない。

HTTP の間隔、User-Agent、キャッシュは各自治体設定の `http` 節に従う。既定の間隔は 3 秒とする。広島県内の新規ソースは 5 秒とする。

## 対象自治体

設定ファイルは `config/sources/{municipalityCode}.yaml` とする。本表に収集不可と書いた自治体には、その yaml も Adapter も置かない。実装の有無は [status.md](status.md) を正とする。

| コード | 自治体 | 実装タイプ | `source.system` | adapter | 収集 |
| --- | --- | --- | --- | --- | --- |
| `281000` | 神戸市 | `html-search` | `dbsr` | `kobe-dbsr` | 可 |
| `340006` | 広島県 | `html-search` | `dbsr` | `dbsr` | 可 |
| `341002` | 広島市 | `html-cgi` | `voices` | `hiroshima-voices` | 可 |
| `342025` | 呉市 | `discuss-json` | `discuss` | `discuss` | 可 |
| `342033` | 竹原市 | `pdf` | | なし | 不可 |
| `342041` | 三原市 | `discuss-json` | `discuss` | `discuss` | 可 |
| `342050` | 尾道市 | `discuss-json` | `discuss` | `discuss` | 可 |
| `342076` | 福山市 | `discuss-json` | `discuss` | `discuss` | 可 |
| `342084` | 府中市 | `html-cgi` | `kensakusystem` | `kensakusystem` | 可 |
| `342092` | 三次市 | `pdf` | | なし | 不可 |
| `342106` | 庄原市 | `discuss-json` | `discuss` | `discuss` | 可 |
| `342114` | 大竹市 | `html-cgi` | `kensakusystem` | `kensakusystem` | 可 |
| `342122` | 東広島市 | `discuss-json` | `discuss` | `discuss` | 可 |
| `342131` | 廿日市市 | `html-search` | `dbsr` | `dbsr` | 可 |
| `342149` | 安芸高田市 | `html-cgi` | `kensakusystem` | `kensakusystem` | 可 |
| `342157` | 江田島市 | `pdf` | | なし | 不可 |
| `343021` | 府中町 | `pdf` | | なし | 不可 |
| `343048` | 海田町 | `pdf` | | なし | 不可 |
| `343072` | 熊野町 | `pdf` | | なし | 不可 |
| `343099` | 坂町 | `pdf` | | なし | 不可 |
| `343684` | 安芸太田町 | `pdf` | | なし | 不可 |
| `343692` | 北広島町 | `pdf` | | なし | 不可 |
| `344311` | 大崎上島町 | `pdf` | | なし | 不可 |
| `344621` | 世羅町 | `pdf` | | なし | 不可 |
| `345458` | 神石高原町 | `discuss-json` | `discuss` | `discuss` | 可 |
| `382019` | 松山市 | `discuss-json` | `discuss` | `discuss` | 可 |

`config/sources/` に yaml があることと、収集可かつ Adapter が実装済みであることは一致させる。収集不可の自治体を yaml だけ置いて CLI から呼べる状態にしてはならない。

## 広島市

```text
municipalityCode: 341002
prefecture: 広島県
実装タイプ: html-cgi
source.system: voices
adapter: hiroshima-voices
入口: https://hiroshima.gijiroku.com/voices/
```

Q'z Creative の VOICES。一覧（`ACT=100`）と本文（`ACT=203`）は CGI の HTML 応答に含まれる。

1 Meeting は会期全体ではなく、日程・号である。Meeting Identity の収集元キーは `FINO`、Speech Identity は `HUID` とする。公開 ID の生成規則は [id.md](id.md) を正とする。

```text
Meeting Identity  = 341002:voices:{FINO}
Speech Identity   = source:{HUID}
```

`KGTP` は会議種類のフィルタであり、公開 ID には使わない。委員会名は原典の表記を保持する。現行名称へ正規化しない。

対象は本会議と、委員会閲覧画面に載っている個別委員会である。「すべて表示」のような集約一覧は DISCOVER しない。年次などの収集範囲は [status.md](status.md) を正とする。

## 広島県議会

```text
municipalityCode: 340006
prefecture: 広島県
実装タイプ: html-search
source.system: dbsr
adapter: dbsr
入口: https://www.pref.hiroshima.dbsr.jp/
```

神戸市会と同じ dbsr 製品の旧 UI。検索結果 HTML に会議へのリンクが含まれる。一覧パス（`/index.php/{viewId}`）はビューアであり、文書ごとに変わることがある。2 ページ目以降は、元の一覧 URL に `Page=` を付けても 1 ページ目が返る。DISCOVER は同一 HTTP セッションで、応答 HTML の `Page=` 付き href をクエリを付け直さずに辿る。ビューア ID が違う同じ `Page=` は辿らない。一覧 GET はキャッシュしない。

`Cabinet=1` は定例会、`Cabinet=2` は臨時会である。本文だけを DISCOVER する。議事日程・名簿および資料は対象外である。

Meeting Identity の収集元キーは `DocumentID` とする。本文 HTML の各発言は `li.page-text__voice` であり、Speech Identity には `VoiceID` を使う。

```text
Meeting Identity  = 340006:dbsr:{DocumentID}
Speech Identity   = source:{VoiceID}
```

対象は本会議の本文のみ。委員会は後続とする。年次は [status.md](status.md) を正とする。

## Discuss

```text
実装タイプ: discuss-json
source.system: discuss
adapter: discuss
入口: https://ssp.kaigiroku.net/tenant/{slug}/MinuteBrowse.html
```

画面上の製品名は Discuss（会議録検索システム）。初期 HTML は殻であり、閲覧 UI が `/dnp/search/` 配下の JSON を POST して一覧と本文を埋める。

許可する経路（閲覧 UI が使うものに限る）:

- `POST /dnp/search/councils/index`（`tenant_id`, `view_years`）
- `POST /dnp/search/minutes/get_schedule`（`tenant_id`, `council_id`）
- `POST /dnp/search/minutes/get_minute`（`tenant_id`, `power_user=false`, `council_id`, `schedule_id`）

検索・統計・ログイン・発言集作成、およびそれ以外の XHR は呼ばない。

1 Meeting は日程・号（`schedule`）である。Meeting Identity の収集元キーは `{council_id}-{schedule_id}`。Speech Identity は `minute_id`。公開 URL は `MinuteView.html?council_id=&schedule_id=`。

```text
Meeting Identity  = {code}:discuss:{council_id}-{schedule_id}
Speech Identity   = source:{minute_id}
```

DISCOVER するのは本会議だけとする。`council_type_name2` が「本会議」のものに限り、委員会と「資料」は対象外である。本文のうち `minute_type_code` が 1（目次）、2（名簿）、9（資料）のブロックは PARSE しない。3（議題）、4（議長）、5（質問）、6（答弁）を残す。

tenant:

| コード | 自治体 | slug | tenantId |
| --- | --- | --- | --- |
| `342025` | 呉市 | kure | 491 |
| `342041` | 三原市 | mihara | 506 |
| `342050` | 尾道市 | onomichi | 274 |
| `342076` | 福山市 | fukuyama | 505 |
| `342106` | 庄原市 | shobara | 339 |
| `342122` | 東広島市 | higashihiroshima | 564 |
| `345458` | 神石高原町 | jinsekikougen | 403 |
| `382019` | 松山市 | matsuyama | 279 |

年次は [status.md](status.md) を正とする。

## 神戸市

```text
municipalityCode: 281000
prefecture: 兵庫県
実装タイプ: html-search
source.system: dbsr
adapter: kobe-dbsr
入口: https://www.city.kobe.hyogo.dbsr.jp/
```

検索結果の HTML に会議へのリンクが含まれる。同じ開催日に本文、議事日程・名簿、資料が別文書として出る。

DISCOVER するのは本文だけとする。議事日程・名簿および資料は対象外である。

Meeting Identity の収集元キーは検索結果の `Id` とする。一覧・本文 URL のパス（例: `/333845`）はビューアであり、文書ごとに変わらない。公開 ID には使わない。

本文 HTML の各発言は `li.voice-block` であり、`data-voice_code` が文書内の発言番号である。Speech Identity にはこれを使う。

```text
Meeting Identity  = 281000:dbsr:{Id}
Speech Identity   = source:{data-voice_code}
```

DISCOVER 対象の例（令和7年第1回定例市会 第6日 本文）は `Id=2020`、開催日 `2025-03-28`、275 発言である。

検索結果一覧は HTTP GET で取る。2 ページ目以降は同じ一覧 URL に `Page` を付けて辿る。画面上のページ送りは POST だが、GET でも同じ HTML が返る。CSRF 付き POST は使わない。

年次、委員会の収集範囲は [status.md](status.md) を正とする。

## 廿日市市

```text
municipalityCode: 342131
prefecture: 広島県
実装タイプ: html-search
source.system: dbsr
adapter: dbsr
入口: https://www.city.hatsukaichi.hiroshima.dbsr.jp/
```

広島県議会と同じ dbsr の旧 UI。検索結果 HTML に会議へのリンクが含まれる。一覧の本文リンクは `Template=doc-one-frame` の frameset であり、県議会が使う `Template=document` は 404 になる。FETCH は同一文書の `Template=doc-page&VoiceType=all` に付け替えて、全発言が入った HTML を取る。1 発言ずつの `doc-page` は辿らない。

`Cabinet=1` は定例会、`Cabinet=2` は臨時会である。本文だけを DISCOVER する。議事日程・名簿および資料は対象外である。委員会は後続とする。

Meeting Identity の収集元キーは `DocumentID`。Speech Identity は `data-voiceno`。

```text
Meeting Identity  = 342131:dbsr:{DocumentID}
Speech Identity   = source:{data-voiceno}
```

年次は [status.md](status.md) を正とする。

## kensakusystem.jp

```text
実装タイプ: html-cgi
source.system: kensakusystem
adapter: kensakusystem
入口: https://www.kensakusystem.jp/{slug}/
```

府中市・大竹市・安芸高田市が使う会議録閲覧 CGI。議会が案内する「会議録の閲覧」（`See.exe`）から辿る。検索（`Search2.exe`）は呼ばない。

`See.exe?Code=` の Code は閲覧セッションであり、文書の Identity ではない。毎回トップ HTML から取り直す。POST は Shift_JIS（cp932）にする。UTF-8 だと年次ツリーが展開されない。

1 Meeting は開催日（`fileName`、例: `R070225A`）。開催日の表記は自治体で差があり、`（ 2月25日）` と `（第1日 3月 3日）` の両方を読む。DISCOVER するのは本会議の定例会・臨時会だけとする。委員会・予算特別委員会・決算特別委員会は対象外である。本文は閲覧画面の全文表示と同じ `GetText3.exe?.../PRINT_ALL/...` の HTML を FETCH する。

```text
Meeting Identity  = {code}:kensakusystem:{fileName}
Speech Identity   = source:{発言順}
```

対象:

| コード | 自治体 | slug |
| --- | --- | --- |
| `342084` | 府中市 | fuchu-c |
| `342114` | 大竹市 | otake |
| `342149` | 安芸高田市 | akitakata |

年次は [status.md](status.md) を正とする。

## 松山市

```text
municipalityCode: 382019
prefecture: 愛媛県
実装タイプ: discuss-json
source.system: discuss
adapter: discuss
入口: https://ssp.kaigiroku.net/tenant/matsuyama/MinuteBrowse.html
```

松山市公式 FAQ も `https://ssp.kaigiroku.net/tenant/matsuyama/pg/index.html` を案内する。画面上の製品名は Discuss。広島県内の Discuss と同じ閲覧 JSON 3 経路と `DiscussAdapter` を使う。`tenantId` は 279、`tenantSlug` は `matsuyama`。

対象は本会議の日程・号のみ。委員会・資料・名簿は対象外である。年次は [status.md](status.md) を正とする。

## 広島県内の見送り

### PDF（不可）

竹原市、三次市、江田島市、府中町、海田町、熊野町、坂町、安芸太田町、北広島町、大崎上島町、世羅町は会議録の正が PDF である。OCR が必要なため当面不可とする。

## 自治体を追加するとき

実装の前に、本文書の対象自治体表と個別節を更新する。コードより先にタイプと収集可否を書く。

手順:

1. 公開入口 URL を確認する
2. 一覧ページと本文ページを、JavaScript なしの HTTP GET で取得する。Discuss は閲覧 UI が使う JSON 3 経路だけを確認する
3. 応答に会議一覧または本文があるか判定する
4. 実装タイプを決める
5. `js-internal-json` または `pdf` なら、収集不可として本文書に残し、Adapter は作らない
6. `html-cgi`、`html-search`、`discuss-json` なら、Meeting Identity の収集元キーを確定してから Adapter を置く

同じ開催日に本文以外の文書（名簿、資料、目次）が並ぶ場合は、本文だけを DISCOVER するかを個別節に書く。委員会名は原典のまま保持する。

PDF を避ける方針は維持する。HTML または Discuss 閲覧 JSON で会議録を公開している自治体を先に足す。広島県内を優先する。

## ベンダー共通 Adapter

同じ製品を使う自治体が複数あり、重複が比較できる段階で共通化する。

- dbsr: 神戸市・広島県議会・廿日市市で成立した。Adapter クラスは共通（`KobeDbsrAdapter`）し、`listingPath` / `queryType` / `cabinets` で差を yaml に置く。登録名は神戸が `kobe-dbsr`、県議会と廿日市市が `dbsr`
- Discuss: 広島県内 7 自治体と松山市で成立した。`DiscussAdapter` を共有し、`tenantId` / `tenantSlug` を yaml に置く
- kensakusystem: 府中市・大竹市・安芸高田市で成立した。`KensakuSystemAdapter` を共有し、`baseUrl` の slug で差を yaml に置く

収集不可の自治体は、その比較対象に数えない。実装済みの Adapter 数は [status.md](status.md) を正とする。
