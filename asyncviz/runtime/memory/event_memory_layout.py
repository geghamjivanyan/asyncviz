"""Event memory-layout helpers.

Constructs :class:`CompactEvent` records from
:class:`RuntimeEvent`s through the configured interner — the
single canonical adapter that the rest of the optimizer + every
caller goes through.
"""

from __future__ import annotations

from typing import Any

from asyncviz.runtime.events.models.base import RuntimeEvent
from asyncviz.runtime.memory.event_interning import StringInterner
from asyncviz.runtime.memory.models.compact_event import (
    CompactEvent,
    CompactEventCategory,
)

_CATEGORY_PREFIXES: tuple[tuple[str, CompactEventCategory], ...] = (
    ("asyncio.task.", "task"),
    ("asyncio.queue.", "queue"),
    ("asyncio.semaphore.", "semaphore"),
    ("asyncio.gather.", "gather"),
    ("asyncio.executor.", "executor"),
    ("runtime.", "runtime"),
)


def categorize_event_type(event_type: str) -> CompactEventCategory:
    """Map an event_type string to its coarse category."""
    # Specific runtime sub-types take precedence over the bare
    # ``runtime.`` prefix.
    if event_type == "runtime.metric":
        return "metric"
    if event_type == "runtime.warning":
        return "warning"
    for prefix, category in _CATEGORY_PREFIXES:
        if event_type.startswith(prefix):
            return category
    return "other"


def _intern_payload(
    payload: dict[str, Any],
    interner: StringInterner,
) -> dict[str, Any]:
    """Intern keys + scalar string values; leave nested
    structures (lists, dicts) alone."""
    out: dict[str, Any] = {}
    for key, value in payload.items():
        interned_key = interner.intern(key) if isinstance(key, str) else key
        interned_value = interner.intern(value) if isinstance(value, str) else value
        out[interned_key] = interned_value
    return out


def compact_from_runtime_event(
    event: RuntimeEvent,
    *,
    interner: StringInterner,
    intern_payload: bool = True,
) -> CompactEvent:
    """Build a :class:`CompactEvent` from a :class:`RuntimeEvent`."""
    payload = event.model_dump(mode="json")
    # Pull the canonical fields up to the envelope.
    event_type = interner.intern(str(payload.get("event_type", "")))
    event_id = str(payload.get("event_id", ""))
    monotonic_ns = int(payload.get("monotonic_ns", 0) or 0)
    wall_time_ns = int(payload.get("wall_time_ns", 0) or 0)
    runtime_id_raw = payload.get("runtime_id", "")
    runtime_id = (
        interner.intern(str(runtime_id_raw))
        if isinstance(runtime_id_raw, str) and runtime_id_raw
        else ""
    )
    # Strip envelope fields from the payload — the compact envelope
    # carries them.
    inner_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"event_type", "event_id", "monotonic_ns", "wall_time_ns", "runtime_id"}
    }
    if intern_payload:
        inner_payload = _intern_payload(inner_payload, interner)
    return CompactEvent(
        event_type=event_type,
        event_id=event_id,
        monotonic_ns=monotonic_ns,
        category=categorize_event_type(event_type),
        payload=inner_payload,
        runtime_id=runtime_id,
        wall_time_ns=wall_time_ns,
    )


def compact_dict_event(
    data: dict[str, Any],
    *,
    interner: StringInterner,
    intern_payload: bool = True,
) -> CompactEvent:
    """Build a :class:`CompactEvent` from a JSON-style event dict
    (e.g. websocket payload, replay frame payload)."""
    event_type_raw = str(data.get("event_type", ""))
    event_type = interner.intern(event_type_raw) if event_type_raw else event_type_raw
    inner_payload_raw = {
        k: v
        for k, v in data.items()
        if k not in {"event_type", "event_id", "monotonic_ns", "wall_time_ns", "runtime_id"}
    }
    inner_payload = (
        _intern_payload(inner_payload_raw, interner) if intern_payload else inner_payload_raw
    )
    return CompactEvent(
        event_type=event_type,
        event_id=str(data.get("event_id", "")),
        monotonic_ns=int(data.get("monotonic_ns", 0) or 0),
        category=categorize_event_type(event_type),
        payload=inner_payload,
        runtime_id=(
            interner.intern(str(data.get("runtime_id", ""))) if data.get("runtime_id") else ""
        ),
        wall_time_ns=int(data.get("wall_time_ns", 0) or 0),
    )
