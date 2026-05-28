"""Websocket-side serialization throughput.

Approximates the bytes/sec we can produce when packing a batch of
runtime events into JSON for websocket dispatch.
"""

from __future__ import annotations

import json

from asyncviz.benchmarks.benchmark_registry import benchmark
from asyncviz.benchmarks.synthetic import build_task_event_stream
from asyncviz.runtime.events.models import to_dict

_EVENTS = build_task_event_stream(count=32)
_PRE_SERIALIZED = [to_dict(e) for e in _EVENTS]


@benchmark(
    name="websocket.serialize.task_batch",
    category="websocket",
    description="json.dumps over a 32-event task batch",
)
def bench_serialize_batch() -> None:
    json.dumps(_PRE_SERIALIZED, separators=(",", ":"))
