"""Websocket cadence compatibility bridge.

uvloop's transport layer batches writes more aggressively than
stock asyncio; under load this changes the effective flush cadence.
The bridge observes flush events + records how often the cadence
deviates from the configured target. It does not *enforce* the
cadence — that's the websocket scheduler's job.

The bridge is decoupled from the actual websocket stack so it can
be unit-tested without sockets: the websocket layer notifies the
bridge of each flush via :meth:`record_flush`; the bridge tracks
the inter-flush intervals + counts anomalies.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from asyncviz.runtime.compat.loop_configuration import LoopCompatConfig


@dataclass(frozen=True, slots=True)
class WebsocketBridgeReport:
    flushes_observed: int
    target_interval_ns: int
    mean_interval_ns: int
    max_interval_ns: int
    deviations_recorded: int
    """How many inter-flush intervals exceeded
    ``target_interval_ns * 1.5`` (or 0 when target is unset)."""


class WebsocketLoopBridge:
    """Observability for websocket flush cadence."""

    __slots__ = (
        "_config",
        "_deviations_recorded",
        "_flushes_observed",
        "_interval_sum_ns",
        "_last_flush_ns",
        "_lock",
        "_max_interval_ns",
        "_target_interval_ns",
    )

    def __init__(
        self,
        config: LoopCompatConfig,
        *,
        target_interval_ns: int = 0,
    ) -> None:
        self._config = config
        self._lock = threading.Lock()
        self._target_interval_ns = max(0, target_interval_ns)
        self._last_flush_ns = 0
        self._flushes_observed = 0
        self._interval_sum_ns = 0
        self._max_interval_ns = 0
        self._deviations_recorded = 0

    @property
    def enabled(self) -> bool:
        return self._config.record_websocket_anomalies

    def set_target_interval_ns(self, target_ns: int) -> None:
        with self._lock:
            self._target_interval_ns = max(0, target_ns)

    def record_flush(self) -> None:
        """Notify the bridge that a websocket flush just completed."""
        if not self.enabled:
            return
        now = time.monotonic_ns()
        with self._lock:
            previous = self._last_flush_ns
            self._last_flush_ns = now
            self._flushes_observed += 1
            if previous == 0:
                return
            interval = now - previous
            self._interval_sum_ns += interval
            if interval > self._max_interval_ns:
                self._max_interval_ns = interval
            if self._target_interval_ns > 0 and interval > self._target_interval_ns * 3 // 2:
                self._deviations_recorded += 1

    def report(self) -> WebsocketBridgeReport:
        with self._lock:
            mean = (
                self._interval_sum_ns // max(1, self._flushes_observed - 1)
                if self._flushes_observed > 1
                else 0
            )
            return WebsocketBridgeReport(
                flushes_observed=self._flushes_observed,
                target_interval_ns=self._target_interval_ns,
                mean_interval_ns=mean,
                max_interval_ns=self._max_interval_ns,
                deviations_recorded=self._deviations_recorded,
            )

    def reset(self) -> None:
        with self._lock:
            self._last_flush_ns = 0
            self._flushes_observed = 0
            self._interval_sum_ns = 0
            self._max_interval_ns = 0
            self._deviations_recorded = 0
