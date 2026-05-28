"""Replay-layer compatibility bridge.

The replay engine reconstructs events at deterministic wall-clock
offsets. Under uvloop the loop clock can advance with slightly
different resolution than under stock asyncio; the replay bridge:

* records a baseline ``(sequence, monotonic_ns)`` pair when replay
  starts,
* exposes a drift-aware "should this loop drive replay?" check,
* counts how many replay frames the bridge has seen + how many
  drifted beyond the configured tolerance.

The bridge does *not* drive replay itself — that's the replay
engine's job. It just provides the timing arbitration the engine
asks for when running under an alternate loop.
"""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass

from asyncviz.runtime.compat.loop_clock_bridge import LoopClockBridge
from asyncviz.runtime.compat.loop_configuration import LoopCompatConfig
from asyncviz.runtime.compat.models.loop_capabilities import LoopCapabilities
from asyncviz.runtime.compat.models.loop_kind import loop_kind_supports_replay


@dataclass(frozen=True, slots=True)
class ReplayLoopReport:
    frames_observed: int
    frames_drifted: int
    max_drift_ns: int
    loop_supports_replay: bool


class ReplayLoopBridge:
    """Coordinates the replay engine with the active loop."""

    __slots__ = (
        "_baseline_monotonic_ns",
        "_baseline_sequence",
        "_clock",
        "_config",
        "_frames_drifted",
        "_frames_observed",
        "_lock",
        "_loop_supports_replay",
        "_max_drift_ns",
    )

    def __init__(self, config: LoopCompatConfig) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._clock = LoopClockBridge(config)
        self._baseline_monotonic_ns = 0
        self._baseline_sequence = 0
        self._loop_supports_replay = True
        self._frames_observed = 0
        self._frames_drifted = 0
        self._max_drift_ns = 0

    def attach(self, capabilities: LoopCapabilities) -> None:
        """Bind the bridge to a probed loop. Idempotent."""
        with self._lock:
            self._loop_supports_replay = (
                capabilities.replay_safe
                and loop_kind_supports_replay(capabilities.kind)
            )

    def start_session(
        self,
        *,
        baseline_sequence: int,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Record the baseline used by :meth:`observe_frame`."""
        with self._lock:
            self._baseline_sequence = baseline_sequence
            self._baseline_monotonic_ns = time.monotonic_ns()
            self._frames_observed = 0
            self._frames_drifted = 0
            self._max_drift_ns = 0
        self._clock.sample(loop)

    def observe_frame(
        self,
        *,
        sequence: int,
        expected_offset_ns: int,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> int:
        """Record one replay frame + return its observed offset.

        ``expected_offset_ns`` is the time the replay engine *thinks*
        should have elapsed since the baseline. The bridge compares
        it against the wall-clock delta + records any drift beyond
        the configured tolerance.
        """
        sample = self._clock.sample(loop)
        observed_ns = sample.monotonic_ns - self._baseline_monotonic_ns
        drift_ns = abs(observed_ns - expected_offset_ns)
        with self._lock:
            self._frames_observed += 1
            if drift_ns > self._config.clock_drift_tolerance_ns:
                self._frames_drifted += 1
            if drift_ns > self._max_drift_ns:
                self._max_drift_ns = drift_ns
        _ = sequence  # accepted for future debugging hooks; presently unused
        return observed_ns

    def replay_safe(self) -> bool:
        with self._lock:
            return self._loop_supports_replay and self._clock.replay_safe()

    def clock_bridge(self) -> LoopClockBridge:
        return self._clock

    def report(self) -> ReplayLoopReport:
        with self._lock:
            return ReplayLoopReport(
                frames_observed=self._frames_observed,
                frames_drifted=self._frames_drifted,
                max_drift_ns=self._max_drift_ns,
                loop_supports_replay=self._loop_supports_replay,
            )

    def reset(self) -> None:
        self._clock.reset()
        with self._lock:
            self._baseline_monotonic_ns = 0
            self._baseline_sequence = 0
            self._frames_observed = 0
            self._frames_drifted = 0
            self._max_drift_ns = 0
