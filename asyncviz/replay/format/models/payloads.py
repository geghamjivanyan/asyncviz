"""Typed payload dataclasses for non-event replay frames.

These dataclasses describe the *shape* of well-known payloads
(snapshots, markers, metadata). They are not required for encoding —
the registry's pass-through codec happily handles raw dicts — but
they give downstream consumers a contract they can rely on.

Each model carries a ``to_dict`` / ``from_dict`` pair so it composes
with :class:`ReplayFrame` without paying for a pydantic model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SnapshotStartPayload:
    """Marks the beginning of a multi-frame snapshot region."""

    snapshot_id: str
    captured_at_ns: int
    sequence_at_capture: int
    kind: str = "full"
    """Snapshot kind — "full" or "incremental"."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "captured_at_ns": self.captured_at_ns,
            "sequence_at_capture": self.sequence_at_capture,
            "kind": self.kind,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SnapshotStartPayload:
        return SnapshotStartPayload(
            snapshot_id=str(data["snapshot_id"]),
            captured_at_ns=int(data["captured_at_ns"]),
            sequence_at_capture=int(data["sequence_at_capture"]),
            kind=str(data.get("kind", "full")),
        )


@dataclass(frozen=True, slots=True)
class SnapshotEndPayload:
    """Marks the end of a snapshot region and reports byte size."""

    snapshot_id: str
    byte_size: int
    delta_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "byte_size": self.byte_size,
            "delta_count": self.delta_count,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SnapshotEndPayload:
        return SnapshotEndPayload(
            snapshot_id=str(data["snapshot_id"]),
            byte_size=int(data["byte_size"]),
            delta_count=int(data.get("delta_count", 0)),
        )


@dataclass(frozen=True, slots=True)
class SnapshotDeltaPayload:
    """One delta inside a snapshot region."""

    snapshot_id: str
    selector: str
    """Dotted path into the snapshot graph the delta updates."""
    op: str
    """One of: ``set`` / ``unset`` / ``append`` / ``merge``."""
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "snapshot_id": self.snapshot_id,
            "selector": self.selector,
            "op": self.op,
        }
        if self.value is not None:
            out["value"] = self.value
        return out

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SnapshotDeltaPayload:
        return SnapshotDeltaPayload(
            snapshot_id=str(data["snapshot_id"]),
            selector=str(data["selector"]),
            op=str(data["op"]),
            value=data.get("value"),
        )


@dataclass(frozen=True, slots=True)
class MarkerPayload:
    """A marker frame's payload — typically a label + free-form
    annotation. Markers are great for seeking and bookmarking."""

    name: str
    labels: tuple[str, ...] = ()
    annotation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "labels": list(self.labels),
            "annotation": self.annotation,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> MarkerPayload:
        labels_raw = data.get("labels") or ()
        return MarkerPayload(
            name=str(data["name"]),
            labels=tuple(str(label) for label in labels_raw),
            annotation=str(data.get("annotation", "")),
        )


@dataclass(frozen=True, slots=True)
class RecordingMetadataPayload:
    """Recording-level metadata frame payload."""

    recording_id: str
    runtime_id: str
    asyncviz_version: str
    started_at_ns: int
    notes: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "recording_id": self.recording_id,
            "runtime_id": self.runtime_id,
            "asyncviz_version": self.asyncviz_version,
            "started_at_ns": self.started_at_ns,
            "notes": dict(self.notes),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RecordingMetadataPayload:
        notes_raw = data.get("notes") or {}
        return RecordingMetadataPayload(
            recording_id=str(data["recording_id"]),
            runtime_id=str(data["runtime_id"]),
            asyncviz_version=str(data["asyncviz_version"]),
            started_at_ns=int(data["started_at_ns"]),
            notes={str(k): str(v) for k, v in notes_raw.items()},
        )


@dataclass(frozen=True, slots=True)
class RuntimeMetadataPayload:
    """Runtime-level metadata frame payload — capability advertise,
    python version, loop kind."""

    python_version: str
    loop_implementation: str
    process_id: int
    hostname: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "python_version": self.python_version,
            "loop_implementation": self.loop_implementation,
            "process_id": self.process_id,
            "hostname": self.hostname,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RuntimeMetadataPayload:
        return RuntimeMetadataPayload(
            python_version=str(data["python_version"]),
            loop_implementation=str(data["loop_implementation"]),
            process_id=int(data["process_id"]),
            hostname=str(data.get("hostname", "")),
        )


@dataclass(frozen=True, slots=True)
class SchemaMetadataPayload:
    """Schema-discovery payload — readers use this to learn what
    envelope/protocol versions a recording was produced under."""

    envelope_version: int
    protocol_version: int
    frame_types: tuple[str, ...]
    payload_types: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_version": self.envelope_version,
            "protocol_version": self.protocol_version,
            "frame_types": list(self.frame_types),
            "payload_types": list(self.payload_types),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SchemaMetadataPayload:
        return SchemaMetadataPayload(
            envelope_version=int(data["envelope_version"]),
            protocol_version=int(data["protocol_version"]),
            frame_types=tuple(str(t) for t in (data.get("frame_types") or ())),
            payload_types=tuple(str(t) for t in (data.get("payload_types") or ())),
        )


@dataclass(frozen=True, slots=True)
class DiagnosticsSummaryPayload:
    """Lightweight diagnostics payload — a snapshot of replay-format
    metrics so an inspector can reconstruct format health without
    talking to the live metrics singleton."""

    frames_encoded: int = 0
    frames_decoded: int = 0
    malformed_frames: int = 0
    validation_failures: int = 0
    migrations_applied: int = 0
    integrity_failures: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "frames_encoded": self.frames_encoded,
            "frames_decoded": self.frames_decoded,
            "malformed_frames": self.malformed_frames,
            "validation_failures": self.validation_failures,
            "migrations_applied": self.migrations_applied,
            "integrity_failures": self.integrity_failures,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> DiagnosticsSummaryPayload:
        return DiagnosticsSummaryPayload(
            frames_encoded=int(data.get("frames_encoded", 0)),
            frames_decoded=int(data.get("frames_decoded", 0)),
            malformed_frames=int(data.get("malformed_frames", 0)),
            validation_failures=int(data.get("validation_failures", 0)),
            migrations_applied=int(data.get("migrations_applied", 0)),
            integrity_failures=int(data.get("integrity_failures", 0)),
        )
