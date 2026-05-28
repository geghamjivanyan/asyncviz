"""Snapshot view of the recorder metrics + trace, suitable for the
diagnostics endpoint."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from asyncviz.runtime.replay.recorder.replay_metrics import (
    RecorderMetricsSnapshot,
    get_recorder_metrics,
)
from asyncviz.runtime.replay.recorder.replay_tracing import (
    RecorderTraceEntry,
    get_recorder_trace,
    is_recorder_trace_enabled,
)


@dataclass(frozen=True, slots=True)
class RecorderDiagnosticsSnapshot:
    metrics: RecorderMetricsSnapshot
    trace_enabled: bool
    trace_count: int
    recent_trace: tuple[RecorderTraceEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "metrics": asdict(self.metrics),
            "trace_enabled": self.trace_enabled,
            "trace_count": self.trace_count,
            "recent_trace": [asdict(entry) for entry in self.recent_trace],
        }


def build_recorder_diagnostics(*, tail: int = 16) -> RecorderDiagnosticsSnapshot:
    trace = get_recorder_trace()
    return RecorderDiagnosticsSnapshot(
        metrics=get_recorder_metrics().snapshot(),
        trace_enabled=is_recorder_trace_enabled(),
        trace_count=len(trace),
        recent_trace=trace[-tail:] if tail > 0 else trace,
    )
