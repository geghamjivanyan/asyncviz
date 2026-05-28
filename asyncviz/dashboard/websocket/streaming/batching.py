"""Lightweight batching primitives.

Today the streaming engine sends one envelope per delta — simple,
deterministic, low-latency. For the high-frequency edge cases a
micro-batching layer can plug in here (a future task).

The primitive is intentionally minimal: a flush window (in ns) and a
max batch size. Real batching needs a buffered send-pump per session;
that lands when subscription topics + selective fanout become real.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BatchingPolicy:
    """Configuration knobs for the future batching layer.

    ``flush_interval_ns=0`` means "no batching" — the engine sends one
    envelope per delta. ``max_batch_size=1`` has the same effect.
    """

    flush_interval_ns: int = 0
    max_batch_size: int = 1

    @property
    def enabled(self) -> bool:
        return self.flush_interval_ns > 0 and self.max_batch_size > 1
