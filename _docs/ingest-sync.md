# 収集・同期

この文書は、定期収集における収集状態、初回同期、増分同期、および同期成功条件を定義します。Collector の処理段階（DISCOVER から EXPORT）とプロセス上の位置づけは [architecture.md](architecture.md) を参照してください。実装の有無は [status.md](status.md) を正とします。

関連:

- 実装状況 → [status.md](status.md)
- Collector Job の段階と作業用 SQLite → [architecture.md](architecture.md)
- 対象自治体と実装タイプ → [sources.md](sources.md)
- EXPORT する Canonical JSON → [data.md](data.md)
- Collector の起動方法 → [cli.md](cli.md)
- 文書の読み順と優先関係 → [README.md](README.md)

## 目次

- [目的](#目的)
- [基本方針](#基本方針)
- [Collection State](#collection-state)
- [初回同期](#初回同期)
- [増分同期](#増分同期)
- [Lookback](#lookback)
- [同期成功条件](#同期成功条件)
- [同期失敗時の扱い](#同期失敗時の扱い)
- [DiscoveryContext](#discoverycontext)
- [設定項目](#設定項目)
- [Adapter との関係](#adapter-との関係)
- [処理フロー](#処理フロー)
- [実装例](#実装例)

## 目的

収集状態管理を過度に複雑化せず、次を実現する。

- 初回収集時に過去データを取得できる
- 2 回目以降は前回同期以降を中心に収集できる
- 最近公開・訂正された過去データを再確認できる
- 一部収集失敗時にデータ欠落を起こしにくい
- Adapter ごとに複雑な状態管理を実装しなくてよい

## 基本方針

収集状態として保持する情報は、原則として `lastSuccessfulSync` のみとする。収集対象自治体ごとに、最後に正常完了した同期時刻を保持する。

収集時には `lastSuccessfulSync - lookbackDays` を起点として再探索する。初回同期では `lastSuccessfulSync` が存在しないため、設定値 `initialFrom` を使用する。

## Collection State

Collection State は自治体単位で管理する。最小データモデルは次とする。

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CollectionState:
    municipality_code: str
    last_successful_sync: datetime | None
```

例:

```json
{
  "municipalityCode": "341002",
  "lastSuccessfulSync": "2026-09-14T10:00:00Z"
}
```

初回収集前は `lastSuccessfulSync` を `null` と同等の状態とする。

### 保管場所

Collection State は data リポジトリへ、自治体 1 ファイルとして保存する。会議 JSON の正本ではない。会議の開催日や検索用 SQLite から導出しない。

```text
{dataRoot}/status/{municipalityCode}.json
```

既定の `dataRoot` は `../local-council-data` である。例:

```text
../local-council-data/status/341002.json
../local-council-data/status/281000.json
```

ファイルの例:

```json
{
  "schemaVersion": "1.0",
  "municipalityCode": "341002",
  "lastSuccessfulSync": "2026-09-14T10:00:00Z"
}
```

ファイルが存在しない、または当該自治体の `lastSuccessfulSync` が空の場合は `lastSuccessfulSync = null` と同等とし、初回同期とする。

Collector Service または専用 Repository のみがこのファイルを読み書きする。Adapter は参照しない。Database Builder と API Server は `status/` を読まない。

同期成功時だけファイルを更新する。失敗時は既存ファイルを残し、会議 JSON だけ書いてよい。試行オプション付きの実行では更新しない。

`var/http-cache/` などのスクラッチデータとは寿命を分ける。HTTP キャッシュは消してよい。`status/` は data リポジトリの Git 履歴として残す。

## 初回同期

`lastSuccessfulSync` が存在しない場合は初回同期とみなす。初回同期では、設定された `initialFrom` 以降の会議を対象とする。

```yaml
collection:
  initialFrom: "2010-01-01"
```

この場合、2010-01-01 以降を探索対象とする。

`initialFrom` が未指定の場合は、Adapter が取得可能な範囲の全期間を対象としてよい。ただし、収集元の仕様上、全期間探索が困難な場合は Adapter 固有の取得可能範囲を使用してよい。

## 増分同期

`lastSuccessfulSync` が存在する場合は増分同期とする。増分同期では、前回成功時刻そのものからではなく、一定期間遡った日時を探索開始点とする。

```text
since = lastSuccessfulSync - lookbackDays
```

例: `lastSuccessfulSync` が 2026-09-14、`lookbackDays` が 30 の場合、2026-08-15 以降を再探索する。

## Lookback

Lookback は、過去会議録の後日追加・訂正を検出するために使用する。デフォルト値は 30 日とする。

```yaml
collection:
  lookbackDays: 30
```

自治体または収集元の特性に応じて変更可能とする。

Lookback 対象に既存会議が含まれる場合、その会議は原則として再取得・再解析する。更新日時や ETag によるスキップは行わない。

## 同期成功条件

同期は、今回の探索対象として認識されたすべての会議について、必要な処理が正常完了した場合のみ成功とする。

成功に必要な処理:

```text
DISCOVER → FETCH → PARSE → NORMALIZE → VALIDATE → EXPORT
```

すべての対象会議が正常処理された場合、`sync = success` とする。同期成功時のみ `lastSuccessfulSync` を今回の同期開始時刻または完了時刻へ更新する。

実装上は、同期開始時刻を記録しておき、その値を保存する方式を推奨する。これにより、同期処理中に新規公開されたデータを次回同期で取りこぼしにくくする。

## 同期失敗時の扱い

1 件以上の会議で処理失敗が発生した場合、同期全体を失敗とする（`sync = failed`）。この場合、`lastSuccessfulSync` を更新してはならない。

例: 対象 100 件のうち成功 99 件、失敗 1 件でも、同期結果は failed とし、`lastSuccessfulSync` は前回値を維持する。

正常処理できた 99 件の Canonical JSON は保存してよい。次回同期では `lastSuccessfulSync` が更新されていないため、失敗した対象を含む範囲が再度探索される。

`partial` 状態は定義しない。同期結果は `success` と `failed` の 2 種類のみとする。

## DiscoveryContext

Adapter へ渡す探索条件は、Collector 側で構築する。

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DiscoveryContext:
    municipality_code: str
    since: datetime | None
```

Adapter は次を実装する。

```python
async def discover(
    self,
    context: DiscoveryContext,
) -> list[MeetingReference]:
    ...
```

Adapter 自身は `initial` / `incremental`、`lastSuccessfulSync`、`lookbackDays` を直接管理しない。これらは Collector Service の責務とする。

## 設定項目

自治体・収集元ごとに、最低限次を設定可能とする。

```yaml
municipalityCode: "341002"
adapter: "voices"

collection:
  initialFrom: "2010-01-01"
  lookbackDays: 30
```

### initialFrom

初回同期の探索開始日。型は `date | null`。未指定時は Adapter が取得可能な全期間を対象としてよい。

### lookbackDays

増分同期時に前回成功時刻から遡る日数。型は 0 以上の整数。推奨デフォルトは 30。

## Adapter との関係

Adapter の責務は、渡された `since` を基準に取得対象会議を発見することである。Adapter は Collection State を保存・更新してはならない。

禁止する例:

```python
class VoicesAdapter:
    async def discover(...):
        state = load_collection_state()
        ...
```

推奨する例:

```python
class VoicesAdapter:
    async def discover(
        self,
        context: DiscoveryContext,
    ) -> list[MeetingReference]:
        ...
```

Collection State の読み書きは Collector Service または専用 Repository が担当する。保存先は `{dataRoot}/status/{municipalityCode}.json` とする。

## 処理フロー

初回同期:

```text
Collection State
lastSuccessfulSync = null
        ↓
initialFrom 取得
        ↓
DiscoveryContext 生成
        ↓
Adapter.discover()
        ↓
収集・変換・検証
        ↓
全件成功
        ↓
lastSuccessfulSync 更新
```

増分同期:

```text
Collection State
lastSuccessfulSync あり
        ↓
lookbackDays を減算
        ↓
since 算出
        ↓
DiscoveryContext 生成
        ↓
Adapter.discover()
        ↓
対象会議を再取得
        ↓
収集・変換・検証
        ↓
全件成功
        ↓
lastSuccessfulSync 更新
```

失敗時:

```text
収集中
   ↓
1件以上失敗
   ↓
sync = failed
   ↓
lastSuccessfulSync 据え置き
```

## 実装例

Collector Service 側の概念実装:

```python
from datetime import datetime, timedelta, timezone


async def collect_municipality(
    municipality_code: str,
    config,
    state_repository,
    adapter,
):
    state = state_repository.get(
        municipality_code
    )

    sync_started_at = datetime.now(
        timezone.utc
    )

    if (
        state is None
        or state.last_successful_sync is None
    ):
        since = config.initial_from
    else:
        since = (
            state.last_successful_sync
            - timedelta(
                days=config.lookback_days
            )
        )

    context = DiscoveryContext(
        municipality_code=municipality_code,
        since=since,
    )

    references = await adapter.discover(
        context
    )

    success = True

    for reference in references:
        try:
            await process_meeting(
                adapter,
                reference,
            )
        except Exception:
            success = False

    if success:
        state_repository.save(
            CollectionState(
                municipality_code=municipality_code,
                last_successful_sync=(
                    sync_started_at
                ),
            )
        )
```

実際の実装では、例外の握り潰しを避け、失敗対象をログへ記録する。

再開カーソル、ETag によるスキップ、`partial` 状態など、本仕様が必須としない事項の実装状況は [status.md](status.md) を正とする。
