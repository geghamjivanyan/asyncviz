"""Clock-source compatibility bridge.

asyncio and uvloop both expose ``loop.time()`` as a monotonic
seconds-since-epoch-ish counter, but the actual source varies — on
Linux uvloop uses libuv's high-resolution monotonic, on macOS it's
mach_absolute_time, and the asyncio variant is
:func:`time.monotonic`. Two different sources means small but real
drift; the replay layer cannot tolerate unbounded drift.

The bridge samples both clocks at construction time + on demand,
reports the delta, and routes the replay layer onto
:func:`time.monotonic_ns` whenever the drift exceeds the configured
tolerance.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from asyncviz.runtime.compat.loop_configuration import LoopCompatConfig


@dataclass(frozen=True, slots=True)
class ClockSample:
    """A single (loop.time, monotonic_ns) sample."""

    loop_time_ns: int
    monotonic_ns: int


@dataclass(frozen=True, slots=True)
class ClockDriftReport:
    samples_observed: int
    last_drift_ns: int
    max_drift_ns: int
    drift_warnings: int
    tolerance_ns: int


class LoopClockBridge:
    """Continuously-measurable drift detector.

    ``loop.time()`` and :func:`time.monotonic_ns` use *different
    epochs* — both are monotonic, but they don't share a reference
    point. Comparing absolute values would produce enormous spurious
    drift. The bridge compares **deltas** against a baseline captured
    on the first :meth:`sample` call.
    """

    __slots__ = (
        "_baseline_loop_ns",
        "_baseline_monotonic_ns",
        "_drift_warnings",
        "_have_baseline",
        "_last_drift_ns",
        "_max_drift_ns",
        "_samples_observed",
        "_tolerance_ns",
    )

    def __init__(self, config: LoopCompatConfig) -> None:
        self._tolerance_ns = config.clock_drift_tolerance_ns
        self._samples_observed = 0
        self._last_drift_ns = 0
        self._max_drift_ns = 0
        self._drift_warnings = 0
        self._baseline_loop_ns = 0
        self._baseline_monotonic_ns = 0
        self._have_baseline = False

    def sample(self, loop: asyncio.AbstractEventLoop | None = None) -> ClockSample:
        """Take one paired sample.

        The first call captures the (loop, monotonic) pair as the
        baseline; later calls compute drift as
        ``|loop_delta - monotonic_delta|``.
        """
        loop_time_ns = self._loop_time_ns(loop)
        monotonic_ns = time.monotonic_ns()
        self._samples_observed += 1
        if not self._have_baseline:
            if loop_time_ns >= 0:
                self._baseline_loop_ns = loop_time_ns
                self._baseline_monotonic_ns = monotonic_ns
                self._have_baseline = True
            self._last_drift_ns = 0
            return ClockSample(loop_time_ns=loop_time_ns, monotonic_ns=monotonic_ns)
        if loop_time_ns < 0:
            self._last_drift_ns = 0
            return ClockSample(loop_time_ns=loop_time_ns, monotonic_ns=monotonic_ns)
        loop_delta = loop_time_ns - self._baseline_loop_ns
        monotonic_delta = monotonic_ns - self._baseline_monotonic_ns
        drift_ns = abs(loop_delta - monotonic_delta)
        self._last_drift_ns = drift_ns
        if drift_ns > self._max_drift_ns:
            self._max_drift_ns = drift_ns
        if drift_ns > self._tolerance_ns:
            self._drift_warnings += 1
        return ClockSample(loop_time_ns=loop_time_ns, monotonic_ns=monotonic_ns)

    def replay_safe(self) -> bool:
        """``True`` while observed drift stays inside the tolerance."""
        return self._last_drift_ns <= self._tolerance_ns

    def report(self) -> ClockDriftReport:
        return ClockDriftReport(
            samples_observed=self._samples_observed,
            last_drift_ns=self._last_drift_ns,
            max_drift_ns=self._max_drift_ns,
            drift_warnings=self._drift_warnings,
            tolerance_ns=self._tolerance_ns,
        )

    def reset(self) -> None:
        self._samples_observed = 0
        self._last_drift_ns = 0
        self._max_drift_ns = 0
        self._drift_warnings = 0
        self._baseline_loop_ns = 0
        self._baseline_monotonic_ns = 0
        self._have_baseline = False

    # ── internals ────────────────────────────────────────────────

    @staticmethod
    def _loop_time_ns(loop: asyncio.AbstractEventLoop | None) -> int:
        candidate = loop
        if candidate is None:
            try:
                candidate = asyncio.get_running_loop()
            except RuntimeError:
                return -1
        try:
            return int(candidate.time() * 1e9)
        except Exception:
            return -1
