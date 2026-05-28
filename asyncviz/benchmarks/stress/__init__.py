"""Stress benchmarks — high-volume workloads that exercise the
runtime under load. Each stress run completes in bounded time."""

from asyncviz.benchmarks.stress import bench_event_storm

__all__ = ["bench_event_storm"]
