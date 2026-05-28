"""Deterministic synthetic workload generators."""

from asyncviz.benchmarks.synthetic.event_workload import (
    build_task_event_stream,
)
from asyncviz.benchmarks.synthetic.recording_workload import (
    build_synthetic_recording,
)

__all__ = ["build_synthetic_recording", "build_task_event_stream"]
