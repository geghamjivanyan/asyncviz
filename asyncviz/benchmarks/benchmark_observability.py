"""Process-wide benchmark metrics."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BenchmarkMetricsSnapshot:
    suites_run: int = 0
    benchmarks_run: int = 0
    benchmarks_ok: int = 0
    benchmarks_failed: int = 0
    benchmarks_insufficient: int = 0
    benchmarks_slow: int = 0
    benchmarks_skipped: int = 0
    regressions_detected: int = 0
    improvements_detected: int = 0
    cumulative_runtime_ns: int = 0


class _Metrics:
    __slots__ = (
        "_benchmarks_failed",
        "_benchmarks_insufficient",
        "_benchmarks_ok",
        "_benchmarks_run",
        "_benchmarks_skipped",
        "_benchmarks_slow",
        "_cumulative_runtime_ns",
        "_improvements_detected",
        "_lock",
        "_regressions_detected",
        "_suites_run",
    )

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reset_locked()

    def _reset_locked(self) -> None:
        self._suites_run = 0
        self._benchmarks_run = 0
        self._benchmarks_ok = 0
        self._benchmarks_failed = 0
        self._benchmarks_insufficient = 0
        self._benchmarks_slow = 0
        self._benchmarks_skipped = 0
        self._regressions_detected = 0
        self._improvements_detected = 0
        self._cumulative_runtime_ns = 0

    def record_suite(self, *, runtime_ns: int) -> None:
        with self._lock:
            self._suites_run += 1
            self._cumulative_runtime_ns += max(0, runtime_ns)

    def record_outcome(self, status: str) -> None:
        with self._lock:
            self._benchmarks_run += 1
            if status == "ok":
                self._benchmarks_ok += 1
            elif status == "failed":
                self._benchmarks_failed += 1
            elif status == "insufficient":
                self._benchmarks_insufficient += 1
            elif status == "slow":
                self._benchmarks_slow += 1
            elif status == "skipped":
                self._benchmarks_skipped += 1

    def record_comparison(self, verdict: str) -> None:
        with self._lock:
            if verdict == "regressed":
                self._regressions_detected += 1
            elif verdict == "improved":
                self._improvements_detected += 1

    def snapshot(self) -> BenchmarkMetricsSnapshot:
        with self._lock:
            return BenchmarkMetricsSnapshot(
                suites_run=self._suites_run,
                benchmarks_run=self._benchmarks_run,
                benchmarks_ok=self._benchmarks_ok,
                benchmarks_failed=self._benchmarks_failed,
                benchmarks_insufficient=self._benchmarks_insufficient,
                benchmarks_slow=self._benchmarks_slow,
                benchmarks_skipped=self._benchmarks_skipped,
                regressions_detected=self._regressions_detected,
                improvements_detected=self._improvements_detected,
                cumulative_runtime_ns=self._cumulative_runtime_ns,
            )

    def reset(self) -> None:
        with self._lock:
            self._reset_locked()


_METRICS: _Metrics | None = None
_METRICS_LOCK = threading.Lock()


def get_benchmark_metrics() -> _Metrics:
    global _METRICS
    if _METRICS is None:
        with _METRICS_LOCK:
            if _METRICS is None:
                _METRICS = _Metrics()
    return _METRICS


def get_benchmark_metrics_snapshot() -> BenchmarkMetricsSnapshot:
    return get_benchmark_metrics().snapshot()


def reset_benchmark_metrics() -> None:
    if _METRICS is not None:
        _METRICS.reset()
