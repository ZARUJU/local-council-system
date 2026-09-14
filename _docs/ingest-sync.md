# 地方議会会議録 収集状態・同期仕様書

## 目次

1. 目的
2. 基本方針
3. Collection State
4. 初回同期
5. 増分同期
6. Lookback
7. 同期成功条件
8. 同期失敗時の扱い
9. DiscoveryContext
10. 設定項目
11. Adapterとの関係
12. 処理フロー
13. 実装例
14. v0.1で採用しない事項

# 1. 目的

本仕様書は、地方議会会議録の定期収集における収集状態、初回同期、増分同期、および同期成功条件を定義する。

本仕様では、収集状態管理を過度に複雑化せず、以下を実現することを目的とする。

* 初回収集時に過去データを取得できる
* 2回目以降は前回同期以降を中心に収集できる
* 最近公開・訂正された過去データを再確認できる
* 一部収集失敗時にデータ欠落を起こしにくい
* Adapterごとに複雑な状態管理を実装しなくてよい

# 2. 基本方針

収集状態として保持する情報は、原則として以下のみとする。

```text
lastSuccessfulSync
```

収集対象自治体ごとに、最後に正常完了した同期時刻を保持する。

収集時には、

```text
lastSuccessfulSync - lookbackDays
```

を起点として再探索する。

初回同期では`lastSuccessfulSync`が存在しないため、設定値`initialFrom`を使用する。

# 3. Collection State

Collection Stateは自治体単位で管理する。

最小データモデルは以下とする。

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

初回収集前は以下と同等の状態とする。

```json
{
  "municipalityCode": "341002",
  "lastSuccessfulSync": null
}
```

# 4. 初回同期

`lastSuccessfulSync`が存在しない場合は初回同期とみなす。

初回同期では、設定された`initialFrom`以降の会議を対象とする。

例:

```yaml
collection:
  initialFrom: "2010-01-01"
```

この場合、

```text
2010-01-01以降
```

を探索対象とする。

`initialFrom`が未指定の場合は、Adapterが取得可能な範囲の全期間を対象としてよい。

ただし、収集元の仕様上、全期間探索が困難な場合はAdapter固有の取得可能範囲を使用してよい。

# 5. 増分同期

`lastSuccessfulSync`が存在する場合は増分同期とする。

増分同期では、前回成功時刻そのものからではなく、一定期間遡った日時を探索開始点とする。

概念:

```text
since
=
lastSuccessfulSync
-
lookbackDays
```

例:

```text
lastSuccessfulSync:
2026-09-14

lookbackDays:
30
```

の場合、

```text
2026-08-15以降
```

を再探索する。

# 6. Lookback

Lookbackは、過去会議録の後日追加・訂正を検出するために使用する。

v0.1ではデフォルト値を以下とする。

```text
30日
```

例:

```yaml
collection:
  lookbackDays: 30
```

自治体または収集元の特性に応じて変更可能とする。

Lookback対象に既存会議が含まれる場合、その会議は原則として再取得・再解析する。

v0.1では、更新日時やETagによるスキップ最適化は必須としない。

# 7. 同期成功条件

同期は、今回の探索対象として認識されたすべての会議について、必要な処理が正常完了した場合のみ成功とする。

成功に必要な処理は以下とする。

```text
DISCOVER
↓
FETCH
↓
PARSE
↓
NORMALIZE
↓
VALIDATE
↓
EXPORT
```

すべての対象会議が正常処理された場合、

```text
sync = success
```

とする。

同期成功時のみ、

```text
lastSuccessfulSync
```

を今回の同期開始時刻または完了時刻へ更新する。

実装上は、同期開始時刻を記録しておき、その値を保存する方式を推奨する。

これにより、同期処理中に新規公開されたデータを次回同期で取りこぼしにくくする。

# 8. 同期失敗時の扱い

1件以上の会議で処理失敗が発生した場合、同期全体を失敗とする。

```text
sync = failed
```

この場合、

```text
lastSuccessfulSync
```

を更新してはならない。

例:

```text
対象会議: 100件

成功: 99件
失敗: 1件
```

の場合、

```text
同期結果 = failed
lastSuccessfulSync = 前回値を維持
```

とする。

正常処理できた99件のCanonical JSONは保存してよい。

次回同期では`lastSuccessfulSync`が更新されていないため、失敗した対象を含む範囲が再度探索される。

v0.1では`partial`状態を定義しない。

同期結果は以下の2種類のみとする。

```text
success
failed
```

# 9. DiscoveryContext

Adapterへ渡す探索条件は、Collector側で構築する。

推奨データモデル:

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DiscoveryContext:
    municipality_code: str
    since: datetime | None
```

Adapterは、

```python
async def discover(
    self,
    context: DiscoveryContext,
) -> list[MeetingReference]:
    ...
```

を実装する。

Adapter自身は、

```text
initial / incremental
lastSuccessfulSync
lookbackDays
```

を直接管理しない。

これらはCollector Serviceの責務とする。

# 10. 設定項目

自治体・収集元ごとに、最低限以下を設定可能とする。

```yaml
municipalityCode: "341002"
adapter: "voices"

collection:
  initialFrom: "2010-01-01"
  lookbackDays: 30
```

## initialFrom

初回同期の探索開始日。

型:

```text
date | null
```

未指定時はAdapterが取得可能な全期間を対象としてよい。

## lookbackDays

増分同期時に前回成功時刻から遡る日数。

型:

```text
integer
```

0以上とする。

推奨デフォルト:

```text
30
```

# 11. Adapterとの関係

Adapterの責務は、渡された`since`を基準に取得対象会議を発見することである。

AdapterはCollection Stateを保存・更新してはならない。

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

Collection Stateの読み書きはCollector Serviceまたは専用Repositoryが担当する。

# 12. 処理フロー

初回同期:

```text
Collection State
lastSuccessfulSync = null
        ↓
initialFrom取得
        ↓
DiscoveryContext生成
        ↓
Adapter.discover()
        ↓
収集・変換・検証
        ↓
全件成功
        ↓
lastSuccessfulSync更新
```

増分同期:

```text
Collection State
lastSuccessfulSyncあり
        ↓
lookbackDaysを減算
        ↓
since算出
        ↓
DiscoveryContext生成
        ↓
Adapter.discover()
        ↓
対象会議を再取得
        ↓
収集・変換・検証
        ↓
全件成功
        ↓
lastSuccessfulSync更新
```

失敗時:

```text
収集中
   ↓
1件以上失敗
   ↓
sync = failed
   ↓
lastSuccessfulSync据え置き
```

# 13. 実装例

Collector Service側の概念実装:

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

# 14. v0.1で採用しない事項

v0.1では以下を必須としない。

* `partial`同期状態
* 会議単位の再開カーソル
* ページ単位の再開位置
* `lastAttemptedSync`
* `lastFailedSync`
* 前回取得URL
* ETagによる差分判定
* Last-Modifiedによる差分判定
* 会議ごとの取得状態永続化
* 複雑なRetry Queue
* Collector Stateの履歴保存

これらは、実際の運用で必要性が確認された場合に追加する。

v0.1では、

```text
Collection State
    lastSuccessfulSync

Collection Config
    initialFrom
    lookbackDays

Sync Result
    success
    failed
```

の最小構成を採用する。
