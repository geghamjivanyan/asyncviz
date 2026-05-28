"""Process-wide counters for the environment loader."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EnvironmentMetricsSnapshot:
    loads: int
    keys_parsed: int
    keys_failed: int
    keys_skipped: int
    overrides_applied: int
    redactions: int


class _EnvironmentMetrics:
    def __init__(self) -> None:
        self._loads = 0
        self._keys_parsed = 0
        self._keys_failed = 0
        self._keys_skipped = 0
        self._overrides_applied = 0
        self._redactions = 0

    def record_load(self) -> None:
        self._loads += 1

    def record_parsed(self, count: int) -> None:
        if count > 0:
            self._keys_parsed += count

    def record_failed(self, count: int) -> None:
        if count > 0:
            self._keys_failed += count

    def record_skipped(self, count: int) -> None:
        if count > 0:
            self._keys_skipped += count

    def record_override(self, count: int = 1) -> None:
        if count > 0:
            self._overrides_applied += count

    def record_redaction(self, count: int = 1) -> None:
        if count > 0:
            self._redactions += count

    def snapshot(self) -> EnvironmentMetricsSnapshot:
        return EnvironmentMetricsSnapshot(
            loads=self._loads,
            keys_parsed=self._keys_parsed,
            keys_failed=self._keys_failed,
            keys_skipped=self._keys_skipped,
            overrides_applied=self._overrides_applied,
            redactions=self._redactions,
        )

    def reset(self) -> None:
        self.__init__()


_instance = _EnvironmentMetrics()


def get_environment_metrics() -> _EnvironmentMetrics:
    return _instance


def reset_environment_metrics() -> None:
    _instance.reset()
