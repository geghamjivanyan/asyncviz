"""Typed payload models for replay frames.

Frame payloads aren't a closed set — the registry accepts arbitrary
dicts so producers can extend the format without modifying this
package. But for the *known* payload shapes (snapshots, markers,
metadata, diagnostics) we keep dataclass models here as the
authoritative reference. They're useful when wiring a replay
consumer that wants typed access to a frame's payload.
"""

from asyncviz.replay.format.models.payloads import (
    DiagnosticsSummaryPayload,
    MarkerPayload,
    RecordingMetadataPayload,
    RuntimeMetadataPayload,
    SchemaMetadataPayload,
    SnapshotDeltaPayload,
    SnapshotEndPayload,
    SnapshotStartPayload,
)

__all__ = [
    "DiagnosticsSummaryPayload",
    "MarkerPayload",
    "RecordingMetadataPayload",
    "RuntimeMetadataPayload",
    "SchemaMetadataPayload",
    "SnapshotDeltaPayload",
    "SnapshotEndPayload",
    "SnapshotStartPayload",
]
