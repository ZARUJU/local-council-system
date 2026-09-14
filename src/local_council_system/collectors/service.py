from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from local_council_system.adapters.base import MinutesAdapter
from local_council_system.collectors.state import (
    CollectionState,
    CollectionStateRepository,
    status_dir_for,
)
from local_council_system.config import SourceConfig
from local_council_system.exporters.data_repo import ensure_data_repo_layout
from local_council_system.exporters.json_exporter import (
    canonical_to_dict,
    export_meeting,
    load_existing_sequences,
    meeting_path,
)
from local_council_system.models import DiscoveryContext, MeetingReference
from local_council_system.normalizers.canonical import to_canonical
from local_council_system.validators.meeting import validate_meeting
from local_council_system.validators.schema import validate_meeting_payload

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectOptions:
    limit: int | None = None
    since: date | None = None
    until: date | None = None
    fino: str | None = None
    discover_only: bool = False
    update_state: bool = True


@dataclass
class CollectResult:
    discovered: int
    succeeded: int
    failed: int
    written: int
    sync_success: bool


class CollectorService:
    def __init__(
        self,
        config: SourceConfig,
        adapter: MinutesAdapter,
        data_root: Path,
        state_repository: CollectionStateRepository | None = None,
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._data_root = data_root
        self._state_repository = state_repository or CollectionStateRepository(
            status_dir_for(data_root)
        )

    def run(self, options: CollectOptions | None = None) -> CollectResult:
        options = options or CollectOptions()
        ensure_data_repo_layout(self._data_root, self._config)
        sync_started_at = datetime.now(timezone.utc)
        context = self._discovery_context(options.since, options.until)
        references = self._adapter.discover(context)
        references = _apply_filters(references, options)
        if options.discover_only:
            for reference in references:
                logger.info(
                    "discovered FINO=%s date=%s title=%s",
                    reference.source_meeting_id,
                    reference.discovered_date,
                    reference.title_hint,
                )
            return CollectResult(
                discovered=len(references),
                succeeded=0,
                failed=0,
                written=0,
                sync_success=False,
            )

        sequences = _assign_sequences(
            references,
            *load_existing_sequences(self._data_root, self._config.municipality_code),
        )
        succeeded = 0
        failed = 0
        written = 0
        for reference in references:
            try:
                sequence = sequences.get(reference.source_meeting_id)
                if sequence is None:
                    raise ValueError("no file sequence for meeting")
                html = self._adapter.fetch(reference)
                parsed = self._adapter.parse(html, reference)
                canonical = to_canonical(
                    parsed,
                    municipality_code=self._config.municipality_code,
                    source_system=self._config.source_system,
                )
                validate_meeting(canonical)
                validate_meeting_payload(canonical_to_dict(canonical))
                path = meeting_path(
                    self._data_root,
                    canonical.municipality_code,
                    canonical.date,
                    sequence,
                )
                if export_meeting(canonical, path):
                    written += 1
                    logger.info("wrote %s speeches=%s", path, len(canonical.speeches))
                else:
                    logger.info("unchanged %s", path)
                succeeded += 1
            except Exception:
                failed += 1
                logger.exception(
                    "failed FINO=%s date=%s",
                    reference.source_meeting_id,
                    reference.discovered_date,
                )

        sync_success = failed == 0 and succeeded == len(references)
        should_update_state = (
            options.update_state
            and options.limit is None
            and options.fino is None
            and options.since is None
            and options.until is None
            and not options.discover_only
            and sync_success
        )
        if should_update_state:
            self._state_repository.save(
                CollectionState(
                    municipality_code=self._config.municipality_code,
                    last_successful_sync=sync_started_at,
                )
            )
        return CollectResult(
            discovered=len(references),
            succeeded=succeeded,
            failed=failed,
            written=written,
            sync_success=sync_success,
        )

    def _discovery_context(
        self,
        since_override: date | None,
        until: date | None,
    ) -> DiscoveryContext:
        state = self._state_repository.get(self._config.municipality_code)
        if since_override is not None:
            since = datetime.combine(since_override, datetime.min.time(), tzinfo=timezone.utc)
        elif state is None or state.last_successful_sync is None:
            since = (
                datetime.combine(
                    self._config.collection.initial_from,
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                )
                if self._config.collection.initial_from
                else None
            )
        else:
            since = state.last_successful_sync - timedelta(
                days=self._config.collection.lookback_days
            )
        until_dt = (
            datetime.combine(until, datetime.max.time(), tzinfo=timezone.utc)
            if until is not None
            else None
        )
        return DiscoveryContext(
            municipality_code=self._config.municipality_code,
            since=since,
            until=until_dt,
        )


def _apply_filters(
    references: list[MeetingReference],
    options: CollectOptions,
) -> list[MeetingReference]:
    filtered = references
    if options.fino is not None:
        filtered = [item for item in filtered if item.source_meeting_id == options.fino]
    if options.limit is not None:
        filtered = filtered[: options.limit]
    return filtered


def _assign_sequences(
    references: list[MeetingReference],
    existing_by_source: dict[str, int] | None = None,
    used_by_date: dict[str, set[int]] | None = None,
) -> dict[str, int]:
    existing_by_source = existing_by_source or {}
    used: dict[str, set[int]] = defaultdict(set)
    for meeting_date, sequences in (used_by_date or {}).items():
        used[meeting_date].update(sequences)

    assigned: dict[str, int] = {}
    pending: dict[date, list[MeetingReference]] = defaultdict(list)
    for reference in references:
        if reference.discovered_date is None:
            continue
        existing = existing_by_source.get(reference.source_meeting_id)
        if existing is not None:
            assigned[reference.source_meeting_id] = existing
            used[reference.discovered_date.isoformat()].add(existing)
            continue
        pending[reference.discovered_date].append(reference)

    for meeting_date, items in pending.items():
        items.sort(key=lambda item: (item.name or "", item.issue or 0, item.source_meeting_id))
        occupied = used[meeting_date.isoformat()]
        next_sequence = 1
        for item in items:
            while next_sequence in occupied:
                next_sequence += 1
            assigned[item.source_meeting_id] = next_sequence
            occupied.add(next_sequence)
            next_sequence += 1
    return assigned
