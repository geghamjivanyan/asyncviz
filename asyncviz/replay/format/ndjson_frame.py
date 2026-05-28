"""Canonical replay frame envelope.

A :class:`ReplayFrame` is the unit of replay-format wire data: one
serialized frame becomes one NDJSON line. The envelope is a frozen
dataclass so the same instance is safe to pass across threads, hash
into integrity sets, and compare structurally during tests.

Design constraints:

* All envelope fields use primitives the JSON codec can round-trip
  losslessly. No datetime objects, no Decimal, no bytes — the format
  is text-only by design.
* Unknown envelope keys land in ``extensions`` so a reader against a
  newer wire revision doesn't drop data.
* ``runtime_id`` / ``recording_id`` / ``wall_time_ns`` are optional
  because some replay sources (offline diagnostics, synthetic
  fixtures) genuinely don't have them, and forcing fake values would
  make the validator weaker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from asyncviz.replay.format.ndjson_schema import (
    ENVELOPE_KEYS,
    REQUIRED_ENVELOPE_KEYS,
    SCHEMA_VERSION,
    FrameType,
)


@dataclass(frozen=True, slots=True)
class ReplayFrame:
    """Canonical envelope for one replay-format frame."""

    schema_version: int
    frame_type: FrameType
    sequence: int
    monotonic_ns: int
    payload_type: str
    payload: dict[str, Any]
    runtime_id: str | None = None
    recording_id: str | None = None
    wall_time_ns: int | None = None
    extensions: dict[str, Any] = field(default_factory=dict)
    """Forward-compatibility bucket. Any envelope key the current
    reader doesn't recognize is stashed here so it survives
    round-tripping through this codec."""

    # ── construction helpers ──────────────────────────────────────

    @staticmethod
    def for_runtime_event(
        *,
        sequence: int,
        monotonic_ns: int,
        payload_type: str,
        payload: dict[str, Any],
        runtime_id: str | None = None,
        recording_id: str | None = None,
        wall_time_ns: int | None = None,
    ) -> ReplayFrame:
        """Build a ``runtime_event`` frame. Convenience factory so
        callers don't need to remember the canonical envelope shape."""
        return ReplayFrame(
            schema_version=SCHEMA_VERSION,
            frame_type="runtime_event",
            sequence=sequence,
            monotonic_ns=monotonic_ns,
            payload_type=payload_type,
            payload=dict(payload),
            runtime_id=runtime_id,
            recording_id=recording_id,
            wall_time_ns=wall_time_ns,
        )

    @staticmethod
    def for_snapshot(
        *,
        kind: str,
        sequence: int,
        monotonic_ns: int,
        payload: dict[str, Any],
        runtime_id: str | None = None,
        recording_id: str | None = None,
        wall_time_ns: int | None = None,
    ) -> ReplayFrame:
        """Build a snapshot_{begin,end,delta} frame."""
        frame_type: FrameType = "snapshot_begin"
        if kind == "end":
            frame_type = "snapshot_end"
        elif kind == "delta":
            frame_type = "snapshot_delta"
        return ReplayFrame(
            schema_version=SCHEMA_VERSION,
            frame_type=frame_type,
            sequence=sequence,
            monotonic_ns=monotonic_ns,
            payload_type=f"snapshot.{kind}",
            payload=dict(payload),
            runtime_id=runtime_id,
            recording_id=recording_id,
            wall_time_ns=wall_time_ns,
        )

    @staticmethod
    def for_marker(
        *,
        sequence: int,
        monotonic_ns: int,
        marker_name: str,
        payload: dict[str, Any] | None = None,
        runtime_id: str | None = None,
        recording_id: str | None = None,
        wall_time_ns: int | None = None,
    ) -> ReplayFrame:
        """Build a marker frame — used for replay seeks + bookmarks."""
        return ReplayFrame(
            schema_version=SCHEMA_VERSION,
            frame_type="marker",
            sequence=sequence,
            monotonic_ns=monotonic_ns,
            payload_type=f"marker.{marker_name}",
            payload=dict(payload or {}),
            runtime_id=runtime_id,
            recording_id=recording_id,
            wall_time_ns=wall_time_ns,
        )

    @staticmethod
    def for_metadata(
        *,
        sequence: int,
        monotonic_ns: int,
        payload_type: str,
        payload: dict[str, Any],
        runtime_id: str | None = None,
        recording_id: str | None = None,
        wall_time_ns: int | None = None,
    ) -> ReplayFrame:
        """Build a metadata frame — schema descriptors, capability
        announcements, recording-level context."""
        return ReplayFrame(
            schema_version=SCHEMA_VERSION,
            frame_type="metadata",
            sequence=sequence,
            monotonic_ns=monotonic_ns,
            payload_type=payload_type,
            payload=dict(payload),
            runtime_id=runtime_id,
            recording_id=recording_id,
            wall_time_ns=wall_time_ns,
        )

    @staticmethod
    def for_diagnostics(
        *,
        sequence: int,
        monotonic_ns: int,
        payload_type: str,
        payload: dict[str, Any],
        runtime_id: str | None = None,
        recording_id: str | None = None,
        wall_time_ns: int | None = None,
    ) -> ReplayFrame:
        """Build a diagnostics frame."""
        return ReplayFrame(
            schema_version=SCHEMA_VERSION,
            frame_type="diagnostics",
            sequence=sequence,
            monotonic_ns=monotonic_ns,
            payload_type=payload_type,
            payload=dict(payload),
            runtime_id=runtime_id,
            recording_id=recording_id,
            wall_time_ns=wall_time_ns,
        )

    # ── dict round-trip ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict ready for canonical JSON encoding.

        Optional fields with value ``None`` are omitted so the wire
        format stays compact — a reader that needs the value can rely
        on default ``None`` via :meth:`from_dict`.
        """
        out: dict[str, Any] = {
            "schema_version": self.schema_version,
            "frame_type": self.frame_type,
            "sequence": self.sequence,
            "monotonic_ns": self.monotonic_ns,
            "payload_type": self.payload_type,
            "payload": self.payload,
        }
        if self.runtime_id is not None:
            out["runtime_id"] = self.runtime_id
        if self.recording_id is not None:
            out["recording_id"] = self.recording_id
        if self.wall_time_ns is not None:
            out["wall_time_ns"] = self.wall_time_ns
        if self.extensions:
            out["extensions"] = self.extensions
        return out

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ReplayFrame:
        """Inverse of :meth:`to_dict`. Tolerates unknown keys by
        stashing them under ``extensions``."""
        missing = REQUIRED_ENVELOPE_KEYS - data.keys()
        if missing:
            raise ValueError(f"frame missing required keys: {sorted(missing)}")
        extensions = {k: v for k, v in data.items() if k not in ENVELOPE_KEYS}
        # Caller might also provide an explicit extensions bucket —
        # merge but let inline extension keys win to avoid silently
        # dropping data.
        explicit_extensions = data.get("extensions") or {}
        if isinstance(explicit_extensions, dict):
            for k, v in explicit_extensions.items():
                extensions.setdefault(k, v)
        return ReplayFrame(
            schema_version=int(data["schema_version"]),
            frame_type=data["frame_type"],
            sequence=int(data["sequence"]),
            monotonic_ns=int(data["monotonic_ns"]),
            payload_type=str(data["payload_type"]),
            payload=dict(data["payload"]) if isinstance(data["payload"], dict) else {},
            runtime_id=data.get("runtime_id"),
            recording_id=data.get("recording_id"),
            wall_time_ns=(
                int(data["wall_time_ns"]) if data.get("wall_time_ns") is not None else None
            ),
            extensions=extensions,
        )
