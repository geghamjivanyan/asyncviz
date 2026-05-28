"""NDJSON replay-format encode/decode microbenchmarks."""

from __future__ import annotations

from asyncviz.benchmarks.benchmark_registry import benchmark
from asyncviz.replay.format import (
    decode_frame,
    encode_frame,
    make_runtime_event_frame,
)
from asyncviz.runtime.events.models import TaskCreatedEvent

_EVENT = TaskCreatedEvent(task_id="t-bench", task_name="bench")
_FRAME = make_runtime_event_frame(sequence=1, monotonic_ns=1_000, event=_EVENT)
_ENCODED = encode_frame(_FRAME)


@benchmark(
    name="replay.format.encode",
    category="replay",
    description="encode_frame on a runtime-event frame",
)
def bench_encode_frame() -> None:
    encode_frame(_FRAME)


@benchmark(
    name="replay.format.decode",
    category="replay",
    description="decode_frame on a canonical NDJSON line",
)
def bench_decode_frame() -> None:
    decode_frame(_ENCODED)
