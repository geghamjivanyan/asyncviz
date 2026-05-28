"""GC control for the benchmark hot path.

Python's cyclic GC fires opportunistically. During a tight
microbenchmark loop that can land *inside* a sample and inject a
multi-ms spike that has nothing to do with the workload. The
``gc_disabled_during`` context manager:

1. Force-collects before disabling so we start the measurement
   window in a known-clean state.
2. Disables the cyclic GC.
3. Re-enables it + collects again on exit so the rest of the
   process doesn't leak.

This is fine for benchmarks because they're transient — the
collection happens *outside* the measurement window so the data
stays representative of the workload + not the collector.
"""

from __future__ import annotations

import gc
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def gc_disabled_during() -> Iterator[None]:
    """Disable cyclic GC for the duration of the block."""
    enabled = gc.isenabled()
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        if enabled:
            gc.enable()
        # Catch up on garbage that piled up during the measurement.
        gc.collect()


def force_gc_round() -> None:
    """Run a complete GC cycle. Called between benchmarks when
    ``isolate_per_benchmark`` is enabled."""
    for _ in range(3):
        gc.collect()
