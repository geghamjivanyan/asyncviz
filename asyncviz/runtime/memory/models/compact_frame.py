"""Compact in-memory replay-frame representation.

Mirrors :class:`asyncviz.replay.format.ReplayFrame` but with a
slim-down for high-volume replay buffers:

* ``frame_type`` + ``payload_type`` are interned.
* The full envelope is collapsed to ``(schema_version, frame_type,
  sequence, monotonic_ns, payload_type, payload)`` — optional fields
  (runtime_id, recording_id, wall_time_ns) are stripped when absent
  so frame instances stay slim.

A round-trip back to :class:`ReplayFrame` is available via
:meth:`to_replay_frame` when the consumer needs the canonical form.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CompactReplayFrame:
    """Compact replay frame."""

    schema_version: int
    frame_type: str
    """Interned envelope kind."""

    sequence: int
    monotonic_ns: int
    payload_type: str
    """Interned payload type."""

    payload: dict[str, Any]
    runtime_id: str = ""
    recording_id: str = ""
    wall_time_ns: int = 0

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "frame_type": self.frame_type,
            "sequence": self.sequence,
            "monotonic_ns": self.monotonic_ns,
            "payload_type": self.payload_type,
            "payload": dict(self.payload),
        }
        if self.runtime_id:
            out["runtime_id"] = self.runtime_id
        if self.recording_id:
            out["recording_id"] = self.recording_id
        if self.wall_time_ns:
            out["wall_time_ns"] = self.wall_time_ns
        return out
