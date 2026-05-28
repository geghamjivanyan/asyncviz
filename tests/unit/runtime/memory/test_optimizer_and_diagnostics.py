"""End-to-end optimizer + diagnostics tests."""

from __future__ import annotations

from asyncviz.runtime.events.models import TaskCreatedEvent
from asyncviz.runtime.memory import (
    EventMemoryOptimizer,
    MemoryOptimizerConfig,
    MemoryThresholdBreach,
    MemoryThresholdMonitor,
    build_memory_diagnostics,
    clear_memory_trace,
    get_memory_trace,
    is_memory_trace_enabled,
    lean_config,
    relaxed_config,
    set_memory_trace_enabled,
)


def test_lean_and_relaxed_configs_pass_validation() -> None:
    assert lean_config().interner_capacity == 1024
    assert relaxed_config().interner_capacity == 65536


def test_invalid_config_raises() -> None:
    import pytest

    with pytest.raises(ValueError):
        MemoryOptimizerConfig(interner_capacity=0)
    with pytest.raises(ValueError):
        MemoryOptimizerConfig(websocket_buffer_bytes=10)


def test_diagnostics_collects_everything(
    optimizer: EventMemoryOptimizer,
) -> None:
    ev = TaskCreatedEvent(task_id="t-1", task_name="hello")
    optimizer.compact_event(ev)
    optimizer.add_topology_edge("a", "b")
    with optimizer.websocket_buffer():
        pass
    diag = optimizer.diagnostics()
    assert diag.interner is not None
    assert diag.topology is not None
    assert diag.topology.node_count == 2
    assert diag.websocket_buffers is not None
    assert diag.metrics.compact_events_built >= 1


def test_threshold_monitor_fires_on_breach() -> None:
    monitor = MemoryThresholdMonitor()
    monitor.set_threshold("interned_strings", 5)
    received: list[MemoryThresholdBreach] = []
    monitor.subscribe(received.append)
    assert monitor.observe("interned_strings", 3) is None
    breach = monitor.observe("interned_strings", 6)
    assert breach is not None
    assert breach.observed == 6
    assert received == [breach]


def test_threshold_monitor_ignores_unknown_metric() -> None:
    monitor = MemoryThresholdMonitor()
    assert monitor.observe("unknown.metric", 1000) is None


def test_tracing_disabled_by_default() -> None:
    assert not is_memory_trace_enabled()
    assert get_memory_trace() == ()


def test_tracing_captures_lifecycle(
    optimizer: EventMemoryOptimizer,
) -> None:
    set_memory_trace_enabled(True)
    try:
        ev = TaskCreatedEvent(task_id="t-1", task_name="hi")
        optimizer.compact_event(ev)
        optimizer.add_topology_edge("p", "c")
        kinds = {entry.kind for entry in get_memory_trace()}
        assert "compact-event-built" in kinds
    finally:
        set_memory_trace_enabled(False)
        clear_memory_trace()


def test_build_memory_diagnostics_standalone() -> None:
    diag = build_memory_diagnostics()
    assert diag.metrics is not None
    assert diag.interner is None
    assert diag.recent_trace == ()


def test_optimizer_reset_clears_all_state(
    optimizer: EventMemoryOptimizer,
) -> None:
    ev = TaskCreatedEvent(task_id="t-1", task_name="hi")
    optimizer.compact_event(ev)
    optimizer.add_topology_edge("a", "b")
    optimizer.reset()
    assert optimizer.interner.stats().size == 0
    assert len(optimizer.topology) == 0
