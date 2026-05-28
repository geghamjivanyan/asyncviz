"""Event-model serialization overhead.

Measures :func:`to_dict` on a representative task event — the
serialization layer is on the hot path for both websocket streaming
and recording.
"""

from __future__ import annotations

from asyncviz.benchmarks.benchmark_registry import benchmark
from asyncviz.benchmarks.synthetic import build_task_event_stream
from asyncviz.runtime.events.models import to_dict

_EVENTS = build_task_event_stream(count=64)


@benchmark(
    name="instrumentation.event.to_dict",
    category="instrumentation",
    description="Serialize 128 runtime events to dict via to_dict",
)
def bench_to_dict_64_events() -> None:
    for event in _EVENTS:
        to_dict(event)
