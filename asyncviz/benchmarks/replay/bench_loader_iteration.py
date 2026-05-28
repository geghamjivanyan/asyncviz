"""Replay loader iteration throughput.

Iterates every frame of a synthetic recording through the loader.
Tracks both raw throughput and effective frames-per-second through
the registry's standard p50/p95/p99 reporting."""

from __future__ import annotations

import tempfile
from pathlib import Path

from asyncviz.benchmarks.benchmark_registry import benchmark
from asyncviz.benchmarks.synthetic import build_synthetic_recording
from asyncviz.replay.loading import ReplayEventLoader


def _build_session() -> tuple[Path, tempfile.TemporaryDirectory]:
    tmp = tempfile.TemporaryDirectory()
    session_dir = Path(tmp.name) / "bench-rec"
    build_synthetic_recording(session_dir, frames_per_chunk=100, chunks=4)
    return session_dir, tmp


_SESSION, _TMP = _build_session()


@benchmark(
    name="replay.loader.iterate_full_recording",
    category="replay",
    description="Iterate every frame of a 400-frame recording via ReplayEventLoader",
)
def bench_loader_iterate_full() -> None:
    with ReplayEventLoader.open(_SESSION) as loader:
        for _ in loader.iter_frames():
            pass
