"""Replay-side memory-layout helpers.

Builds :class:`CompactReplayFrame` records from canonical
:class:`ReplayFrame` objects through the interner. Inverse of
:func:`compact_from_runtime_event` for the replay-format side.
"""

from __future__ import annotations

from typing import Any

from asyncviz.replay.format import ReplayFrame
from asyncviz.runtime.memory.event_interning import StringInterner
from asyncviz.runtime.memory.event_memory_layout import _intern_payload
from asyncviz.runtime.memory.models.compact_frame import CompactReplayFrame


def compact_replay_frame(
    frame: ReplayFrame,
    *,
    interner: StringInterner,
    intern_payload: bool = True,
) -> CompactReplayFrame:
    """Build a :class:`CompactReplayFrame` from a canonical
    :class:`ReplayFrame`."""
    payload = _intern_payload(frame.payload, interner) if intern_payload else dict(frame.payload)
    return CompactReplayFrame(
        schema_version=frame.schema_version,
        frame_type=interner.intern(str(frame.frame_type)),
        sequence=frame.sequence,
        monotonic_ns=frame.monotonic_ns,
        payload_type=interner.intern(str(frame.payload_type)),
        payload=payload,
        runtime_id=interner.intern(frame.runtime_id) if frame.runtime_id else "",
        recording_id=interner.intern(frame.recording_id) if frame.recording_id else "",
        wall_time_ns=frame.wall_time_ns or 0,
    )


def compact_replay_dict(
    data: dict[str, Any],
    *,
    interner: StringInterner,
    intern_payload: bool = True,
) -> CompactReplayFrame:
    """Build a compact frame from a JSON-style frame dict."""
    payload_raw = data.get("payload") or {}
    payload = _intern_payload(payload_raw, interner) if intern_payload else dict(payload_raw)
    return CompactReplayFrame(
        schema_version=int(data.get("schema_version", 1)),
        frame_type=interner.intern(str(data.get("frame_type", ""))),
        sequence=int(data.get("sequence", 0)),
        monotonic_ns=int(data.get("monotonic_ns", 0) or 0),
        payload_type=interner.intern(str(data.get("payload_type", ""))),
        payload=payload,
        runtime_id=(
            interner.intern(str(data.get("runtime_id", ""))) if data.get("runtime_id") else ""
        ),
        recording_id=(
            interner.intern(str(data.get("recording_id", ""))) if data.get("recording_id") else ""
        ),
        wall_time_ns=int(data.get("wall_time_ns", 0) or 0),
    )
