"""Websocket-side sampling helper.

Wraps :class:`EventSampler` with the websocket bridge's needs:

* Pressure signal = websocket outbound queue depth.
* Per-subscriber shedding — when one viewer falls behind, the
  sampler tightens up *for that viewer's stream*, not the global
  bus.
* Compact decision-result that the bridge can serialize alongside
  the dispatched frame (so downstream tools see *why* an event was
  dropped).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.runtime.sampling.event_sampler import EventSampler
from asyncviz.runtime.sampling.models.sampling_decision import SamplingDecision
from asyncviz.runtime.sampling.models.sampling_priority import SamplingPriority


@dataclass(slots=True)
class WebsocketSheddingStats:
    queue_depth_high: int = 0
    queue_depth_low: int = 0
    """Hysteresis bands."""

    times_shed_engaged: int = 0
    times_shed_released: int = 0
    last_queue_depth: int = 0


class WebsocketSamplingController:
    """Per-subscriber shedding controller."""

    __slots__ = (
        "_engaged",
        "_high_watermark",
        "_lock",
        "_low_watermark",
        "_sampler",
        "_stats",
    )

    def __init__(
        self,
        *,
        sampler: EventSampler,
        queue_high_watermark: int = 4096,
        queue_low_watermark: int = 1024,
    ) -> None:
        if queue_low_watermark >= queue_high_watermark:
            raise ValueError(
                "queue_low_watermark must be < queue_high_watermark",
            )
        self._sampler = sampler
        self._high_watermark = queue_high_watermark
        self._low_watermark = queue_low_watermark
        self._lock = threading.Lock()
        self._engaged = False
        self._stats = WebsocketSheddingStats(
            queue_depth_high=queue_high_watermark,
            queue_depth_low=queue_low_watermark,
        )

    @property
    def engaged(self) -> bool:
        with self._lock:
            return self._engaged

    def observe_queue_depth(self, depth: int) -> bool:
        """Feed one queue-depth reading. Returns the new engaged
        state."""
        with self._lock:
            self._stats.last_queue_depth = depth
            if not self._engaged and depth >= self._high_watermark:
                self._engaged = True
                self._stats.times_shed_engaged += 1
                self._sampler.set_overload(True)
            elif self._engaged and depth <= self._low_watermark:
                self._engaged = False
                self._stats.times_shed_released += 1
                self._sampler.set_overload(False)
            return self._engaged

    def should_send(
        self,
        event_type: str,
        *,
        priority: SamplingPriority | None = None,
    ) -> SamplingDecision:
        """Single entry point the bridge calls per outbound event.

        Returns a decision; the bridge keeps + sends the frame only
        when ``decision.retain`` is True."""
        return self._sampler.evaluate(event_type, priority=priority)

    def stats(self) -> WebsocketSheddingStats:
        with self._lock:
            return WebsocketSheddingStats(
                queue_depth_high=self._stats.queue_depth_high,
                queue_depth_low=self._stats.queue_depth_low,
                times_shed_engaged=self._stats.times_shed_engaged,
                times_shed_released=self._stats.times_shed_released,
                last_queue_depth=self._stats.last_queue_depth,
            )

    def reset(self) -> None:
        with self._lock:
            self._engaged = False
            self._stats = WebsocketSheddingStats(
                queue_depth_high=self._high_watermark,
                queue_depth_low=self._low_watermark,
            )
