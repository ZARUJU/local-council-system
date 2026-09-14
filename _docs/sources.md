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
- [神戸市](#神戸市)
- [松山市](#松山市)
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
| `js-internal-json` | 閲覧用 HTML は殻だけで、一覧・本文が画面専用の内部 JSON / XHR で埋まる | 不可 |
| `pdf` | 会議録の正が PDF | 当面不可 |

`html-cgi` と `html-search` は、ブラウザで URL を開けば会議録またはその一覧が応答本文に出る点で同じである。検索画面の有無や CGI パラメータの違いは Adapter 内に閉じる。

`js-internal-json` は、利用者が画面上で読めることと、Collector が同じ内容を公開 HTTP として取得できることが一致しない。このタイプは Adapter を置かない。

`pdf` は OCR やページ単位の解析が必要なため、当面は対象外とする。実装しない機能の一覧は [status.md](status.md) を正とする。

## 収集してよい原資料

Collector が FETCH してよいのは、次をすべて満たすものに限る。

- ログインなしで取得できる
- 自治体または議会が会議録の閲覧・検索用として案内している入口から辿れる
- HTTP 応答そのものに、一覧または本文が含まれる（HTML を含む）

次は FETCH しない。

- 公式の公開 API として案内されていない、画面専用の内部 JSON / JSONP / XHR
- 認証後にだけ見える会議録
- 利用規約または robots.txt が取得を禁じている経路

画面の Network パネルで JSON が見えること、認証なしでその JSON が返ることだけでは、公開 API とはみなさない。

DISCOVER も同様である。初期 HTML に会議一覧が無く、内部 JSON を呼ばないと列挙できない場合は、その自治体を実装しない。HTML に会議への公開 URL が安定して含まれるようになった場合、または公式の公開 API が案内された場合に、本文書のタイプと方針を更新してから実装する。

HTTP の間隔、User-Agent、キャッシュは各自治体設定の `http` 節に従う。既定の間隔は 3 秒とする。

## 対象自治体

設定ファイルは `config/sources/{municipalityCode}.yaml` とする。本表に収集不可と書いた自治体には、その yaml も Adapter も置かない。実装の有無は [status.md](status.md) を正とする。

| コード | 自治体 | 実装タイプ | `source.system` | adapter | 収集 |
| --- | --- | --- | --- | --- | --- |
| `341002` | 広島市 | `html-cgi` | `voices` | `hiroshima-voices` | 可 |
| `281000` | 神戸市 | `html-search` | `dbsr` | `kobe-dbsr` | 可 |
| `382019` | 松山市 | `js-internal-json` | `discuss` | なし | 不可 |

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

年次、ページング、委員会の収集範囲は [status.md](status.md) を正とする。

## 松山市

```text
municipalityCode: 382019
prefecture: 愛媛県
実装タイプ: js-internal-json
source.system: discuss
adapter: なし
収集: 不可
入口: https://ssp.kaigiroku.net/tenant/matsuyama/pg/index.html
```

松山市公式 FAQ が案内する会議録検索の入口である。画面上の製品名は Discuss（会議録検索システム）である。

閲覧（`MinuteBrowse.html`）は年・会議種類・会議の階層を持つ。ただし初期 HTML には会議一覧が無い。本文ページも殻であり、発言は JavaScript が後から埋める。

調査の結果、画面は `/dnp/search/` 配下の内部 JSON を呼んで一覧と本文を組み立てている。これは公式の公開 API として案内されていない。認証なしで JSON が返ることと、Collector がそれを使ってよいことは別である。

方針:

- Adapter、設定 yaml、Parser、fixture を置かない
- `/dnp/search/` および同等の画面専用 JSON を Collector から呼び出さない
- HTML に会議一覧や本文が安定して含まれるようになった場合、または公式の公開 API が案内された場合に限り、本節のタイプと収集可否を更新してから実装する
- その更新がないまま、内部 JSON を叩く実装を再開してはならない

見送りの理由は技術的な取得不能ではない。公開ページの HTML を読む広島・神戸と同じ収集形態として扱えない、という判断である。

## 自治体を追加するとき

実装の前に、本文書の対象自治体表と個別節を更新する。コードより先にタイプと収集可否を書く。

手順:

1. 公開入口 URL を確認する
2. 一覧ページと本文ページを、JavaScript なしの HTTP GET で取得する
3. 応答 HTML に会議一覧または本文があるか判定する
4. 実装タイプを決める
5. `js-internal-json` または `pdf` なら、収集不可として本文書に残し、Adapter は作らない
6. `html-cgi` または `html-search` なら、Meeting Identity の収集元キーを確定してから Adapter を置く

同じ開催日に本文以外の文書（名簿、資料、目次）が並ぶ場合は、本文だけを DISCOVER するかを個別節に書く。委員会名は原典のまま保持する。

PDF を避ける方針は維持する。HTML で会議録を公開している自治体を先に足す。

## ベンダー共通 Adapter

同じ製品（VOICES、dbsr、Discuss 等）を使う自治体が複数あっても、実装済みが 1 自治体のうちは製品共通の Base Adapter を作らない。

共通化は、同じ実装タイプの Adapter が複数成立し、重複が比較できる段階で行う。収集不可の自治体は、その比較対象に数えない。

実装済みの Adapter 数は [status.md](status.md) を正とする。
