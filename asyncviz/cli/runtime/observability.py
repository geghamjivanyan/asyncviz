"""Lightweight CLI metrics collector.

Same pattern as the other observability modules in the codebase — one
process-wide instance, snapshot-by-value, tests reset between runs.
The metrics are deliberately tiny: counts + durations for the events
that matter for the CLI UX (parse → spawn → ready → exit).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CliMetricsSnapshot:
    """Public counters surface."""

    runs_started: int
    runs_succeeded: int
    runs_failed: int
    bootstrap_failures: int
    subprocess_launches: int
    signal_forwards: int
    browser_launches: int
    browser_skips: int
    average_parse_ms: float
    last_run_total_ms: float
    last_run_subprocess_ms: float


class _CliMetrics:
    def __init__(self) -> None:
        self._runs_started = 0
        self._runs_succeeded = 0
        self._runs_failed = 0
        self._bootstrap_failures = 0
        self._subprocess_launches = 0
        self._signal_forwards = 0
        self._browser_launches = 0
        self._browser_skips = 0
        self._parse_total_ms = 0.0
        self._parse_samples = 0
        self._last_run_total_ms = 0.0
        self._last_run_subprocess_ms = 0.0

    def record_run_started(self) -> None:
        self._runs_started += 1

    def record_run_outcome(self, *, ok: bool) -> None:
        if ok:
            self._runs_succeeded += 1
        else:
            self._runs_failed += 1

    def record_bootstrap_failure(self) -> None:
        self._bootstrap_failures += 1

    def record_subprocess_launch(self) -> None:
        self._subprocess_launches += 1

    def record_signal_forward(self) -> None:
        self._signal_forwards += 1

    def record_browser_launch(self, *, opened: bool) -> None:
        if opened:
            self._browser_launches += 1
        else:
            self._browser_skips += 1

    def record_parse_duration(self, ms: float) -> None:
        if ms < 0 or ms != ms:  # NaN guard
            return
        self._parse_total_ms += ms
        self._parse_samples += 1

    def record_run_durations(self, *, total_ms: float, subprocess_ms: float) -> None:
        self._last_run_total_ms = max(0.0, total_ms)
        self._last_run_subprocess_ms = max(0.0, subprocess_ms)

    def snapshot(self) -> CliMetricsSnapshot:
        avg = 0.0 if self._parse_samples == 0 else self._parse_total_ms / self._parse_samples
        return CliMetricsSnapshot(
            runs_started=self._runs_started,
            runs_succeeded=self._runs_succeeded,
            runs_failed=self._runs_failed,
            bootstrap_failures=self._bootstrap_failures,
            subprocess_launches=self._subprocess_launches,
            signal_forwards=self._signal_forwards,
            browser_launches=self._browser_launches,
            browser_skips=self._browser_skips,
            average_parse_ms=avg,
            last_run_total_ms=self._last_run_total_ms,
            last_run_subprocess_ms=self._last_run_subprocess_ms,
        )

    def reset(self) -> None:
        self.__init__()


_instance = _CliMetrics()


def get_cli_metrics() -> _CliMetrics:
    return _instance


def reset_cli_metrics() -> None:
    _instance.reset()
