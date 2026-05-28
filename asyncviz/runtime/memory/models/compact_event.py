"""Compact in-memory event representation.

A :class:`CompactEvent` carries the minimum the runtime + replay
need from a fully-featured :class:`RuntimeEvent`:

* event_type (interned)
* event_id (raw — usually a UUID, no benefit from interning)
* monotonic_ns
* a small typed payload dict whose string keys + string values are
  also interned

Why a separate model? :class:`RuntimeEvent` subclasses inherit from
``BaseModel`` and carry pydantic validation machinery — perfect for
the API surface, expensive for high-volume in-memory storage. The
compact form is suitable for:

* recorder buffers (millions of events in flight)
* websocket queues (large fanout)
* topology adjacency caches

A round-trip back to a :class:`RuntimeEvent` is *lossy* on
production-only fields (e.g. computed properties) but reversible
for the canonical payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CompactEventCategory = Literal[
    "task",
    "queue",
    "semaphore",
    "gather",
    "executor",
    "runtime",
    "metric",
    "warning",
    "other",
]


@dataclass(frozen=True, slots=True)
class CompactEvent:
    """Compact event record."""

    event_type: str
    """Interned event-type string."""

    event_id: str
    """UUID string. Not interned (each event has a unique id)."""

    monotonic_ns: int
    category: CompactEventCategory
    payload: dict[str, Any]
    """Compact payload — keys + scalar values are interned. Nested
    dicts/lists are not recursively interned (the cost outweighs
    benefits beyond the first level for typical payloads)."""

    runtime_id: str = ""
    """Optional interned runtime-id pointer."""

    wall_time_ns: int = 0
    """0 when not captured."""

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict for serialization."""
        out: dict[str, Any] = {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "monotonic_ns": self.monotonic_ns,
            "category": self.category,
            "payload": dict(self.payload),
        }
        if self.runtime_id:
            out["runtime_id"] = self.runtime_id
        if self.wall_time_ns:
            out["wall_time_ns"] = self.wall_time_ns
        return out
