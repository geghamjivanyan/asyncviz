"""Process-wide counters for the asset subsystem."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AssetMetricsSnapshot:
    publishes_attempted: int
    publishes_succeeded: int
    publishes_failed: int
    files_copied_total: int
    files_removed_total: int
    validations_performed: int
    validation_failures: int
    cache_hits: int
    cache_misses: int


class _AssetMetrics:
    def __init__(self) -> None:
        self._publishes_attempted = 0
        self._publishes_succeeded = 0
        self._publishes_failed = 0
        self._files_copied = 0
        self._files_removed = 0
        self._validations = 0
        self._validation_failures = 0
        self._cache_hits = 0
        self._cache_misses = 0

    def record_publish(self, *, ok: bool, files_copied: int = 0, files_removed: int = 0) -> None:
        self._publishes_attempted += 1
        if ok:
            self._publishes_succeeded += 1
        else:
            self._publishes_failed += 1
        self._files_copied += max(0, files_copied)
        self._files_removed += max(0, files_removed)

    def record_validation(self, *, ok: bool) -> None:
        self._validations += 1
        if not ok:
            self._validation_failures += 1

    def record_cache_hit(self) -> None:
        self._cache_hits += 1

    def record_cache_miss(self) -> None:
        self._cache_misses += 1

    def snapshot(self) -> AssetMetricsSnapshot:
        return AssetMetricsSnapshot(
            publishes_attempted=self._publishes_attempted,
            publishes_succeeded=self._publishes_succeeded,
            publishes_failed=self._publishes_failed,
            files_copied_total=self._files_copied,
            files_removed_total=self._files_removed,
            validations_performed=self._validations,
            validation_failures=self._validation_failures,
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
        )

    def reset(self) -> None:
        self.__init__()


_instance = _AssetMetrics()


def get_asset_metrics() -> _AssetMetrics:
    return _instance


def reset_asset_metrics() -> None:
    _instance.reset()
