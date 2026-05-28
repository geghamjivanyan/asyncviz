"""Event compaction adapter.

The single entry point callers use to turn runtime events into
:class:`CompactEvent`s. Wraps :func:`compact_from_runtime_event`
with metrics + tracing so observability stays consistent across
every call site.
"""

from __future__ import annotations

from asyncviz.runtime.events.models.base import RuntimeEvent
from asyncviz.runtime.memory.event_interning import StringInterner
from asyncviz.runtime.memory.event_memory_layout import (
    compact_dict_event,
    compact_from_runtime_event,
)
from asyncviz.runtime.memory.memory_observability import get_memory_metrics
from asyncviz.runtime.memory.memory_tracing import record_memory_trace
from asyncviz.runtime.memory.models.compact_event import CompactEvent


def compact_event(
    event: RuntimeEvent,
    *,
    interner: StringInterner,
    intern_payload: bool = True,
) -> CompactEvent:
    """Compact + record metrics."""
    compact = compact_from_runtime_event(
        event, interner=interner, intern_payload=intern_payload,
    )
    get_memory_metrics().record_compact_event()
    record_memory_trace(
        "compact-event-built", f"type={compact.event_type}",
    )
    return compact


def compact_dict(
    data: dict, *, interner: StringInterner, intern_payload: bool = True,  # type: ignore[type-arg]
) -> CompactEvent:
    compact = compact_dict_event(
        data, interner=interner, intern_payload=intern_payload,
    )
    get_memory_metrics().record_compact_event()
    return compact
