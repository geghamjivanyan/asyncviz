"""Instrumentation-overhead benchmarks.

Importing this package registers every benchmark inside it with the
global registry. Benchmarks compare instrumented vs baseline paths
of the runtime instrumentation surface.
"""

from asyncviz.benchmarks.instrumentation import (
    bench_event_bus_publish,
    bench_event_serialization,
)

__all__ = ["bench_event_bus_publish", "bench_event_serialization"]
