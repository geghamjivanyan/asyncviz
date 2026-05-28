"""Composed diagnostics snapshot for the recording subsystem."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from asyncviz.replay.recording.recording_manifest import read_manifest
from asyncviz.replay.recording.recording_observability import (
    RecordingMetricsSnapshot,
    get_recording_metrics,
)
from asyncviz.replay.recording.recording_tracing import (
    RecordingTraceEntry,
    get_recording_trace,
    is_recording_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class RecordingDiagnostics:
    metrics: RecordingMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[RecordingTraceEntry, ...]
    session_dir: str | None
    manifest_present: bool
    chunk_count: int
    event_count: int
    last_sequence: int
    finalized: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": asdict(self.metrics),
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [asdict(e) for e in self.recent_trace],
            "session_dir": self.session_dir,
            "manifest_present": self.manifest_present,
            "chunk_count": self.chunk_count,
            "event_count": self.event_count,
            "last_sequence": self.last_sequence,
            "finalized": self.finalized,
        }


def build_recording_diagnostics(
    *,
    session_dir: Path | None = None,
    tail: int = 16,
) -> RecordingDiagnostics:
    metadata = None
    chunk_count = 0
    event_count = 0
    last_sequence = 0
    finalized = False
    manifest_present = False
    if session_dir is not None:
        try:
            metadata = read_manifest(session_dir)
        except ValueError:
            metadata = None
        manifest_present = (session_dir / "manifest.json").exists()
        if metadata is not None:
            chunk_count = metadata.chunk_count
            event_count = metadata.event_count
            last_sequence = metadata.last_sequence
            finalized = metadata.finalized
    trace = get_recording_trace()
    return RecordingDiagnostics(
        metrics=get_recording_metrics().snapshot(),
        trace_enabled=is_recording_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
        session_dir=str(session_dir) if session_dir is not None else None,
        manifest_present=manifest_present,
        chunk_count=chunk_count,
        event_count=event_count,
        last_sequence=last_sequence,
        finalized=finalized,
    )
