"""Sampling-priority model.

Every event lands in one of four priority tiers. The tier drives
every downstream decision (retention rate, websocket shedding,
replay marker emission).

* :attr:`CRITICAL` — warnings, errors, runtime lifecycle. Never
  dropped under any policy.
* :attr:`STRUCTURAL` — topology mutations (task created/completed,
  queue created, gather created/completed). Default 100% retention
  because dropping any of these *corrupts* downstream replay state.
* :attr:`STATE` — periodic state updates + metrics. Sampled
  proportional to load.
* :attr:`DELTA` — repetitive deltas (saturation pings, throughput
  ticks). Sampled aggressively.

The classifier maps `event_type` strings to priorities; callers can
override per-event when they know better than the default mapping.
"""

from __future__ import annotations

from enum import IntEnum


class SamplingPriority(IntEnum):
    """Ordered priority — *higher value = more important*."""

    DELTA = 1
    STATE = 2
    STRUCTURAL = 3
    CRITICAL = 4


# Event-type → priority. Ordered by specificity (most specific
# prefixes first) so the classifier returns the right tier on the
# first match.
_PRIORITY_PREFIXES: tuple[tuple[str, SamplingPriority], ...] = (
    # ── critical ──
    ("runtime.warning", SamplingPriority.CRITICAL),
    ("runtime.started", SamplingPriority.CRITICAL),
    ("runtime.stopped", SamplingPriority.CRITICAL),
    ("asyncio.loop.blocked", SamplingPriority.CRITICAL),
    # ── structural ──
    ("asyncio.task.created", SamplingPriority.STRUCTURAL),
    ("asyncio.task.completed", SamplingPriority.STRUCTURAL),
    ("asyncio.task.cancelled", SamplingPriority.STRUCTURAL),
    ("asyncio.task.failed", SamplingPriority.STRUCTURAL),
    ("asyncio.queue.created", SamplingPriority.STRUCTURAL),
    ("asyncio.queue.cancelled", SamplingPriority.STRUCTURAL),
    ("asyncio.semaphore.created", SamplingPriority.STRUCTURAL),
    ("asyncio.gather.created", SamplingPriority.STRUCTURAL),
    ("asyncio.gather.completed", SamplingPriority.STRUCTURAL),
    ("asyncio.gather.cancelled", SamplingPriority.STRUCTURAL),
    ("asyncio.gather.failed", SamplingPriority.STRUCTURAL),
    ("asyncio.executor.registered", SamplingPriority.STRUCTURAL),
    # Structural state changes deeper in the trees.
    ("asyncio.gather.child.attached", SamplingPriority.STRUCTURAL),
    # ── delta (most repetitive) ──
    ("asyncio.queue.metrics.updated", SamplingPriority.DELTA),
    ("asyncio.executor.metrics.updated", SamplingPriority.DELTA),
    ("asyncio.executor.saturation.changed", SamplingPriority.DELTA),
    ("asyncio.queue.pressure.changed", SamplingPriority.DELTA),
    ("asyncio.queue.saturation.detected", SamplingPriority.DELTA),
    ("asyncio.executor.contention.detected", SamplingPriority.DELTA),
    ("asyncio.executor.latency.spike.detected", SamplingPriority.DELTA),
    ("asyncio.queue.contention.detected", SamplingPriority.DELTA),
    ("asyncio.semaphore.contention.detected", SamplingPriority.DELTA),
    ("runtime.metric", SamplingPriority.DELTA),
)

_CATEGORY_DEFAULTS: tuple[tuple[str, SamplingPriority], ...] = (
    ("asyncio.task.", SamplingPriority.STATE),
    ("asyncio.queue.", SamplingPriority.STATE),
    ("asyncio.semaphore.", SamplingPriority.STATE),
    ("asyncio.gather.", SamplingPriority.STATE),
    ("asyncio.executor.", SamplingPriority.STATE),
    ("runtime.", SamplingPriority.STATE),
)


def classify_event_priority(event_type: str) -> SamplingPriority:
    """Map an event_type string to its sampling priority."""
    # Specific overrides win.
    for prefix, priority in _PRIORITY_PREFIXES:
        if event_type == prefix or event_type.startswith(prefix + "."):
            return priority
    # Category defaults.
    for prefix, priority in _CATEGORY_DEFAULTS:
        if event_type.startswith(prefix):
            return priority
    return SamplingPriority.STATE
