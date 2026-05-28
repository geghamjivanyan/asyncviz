import time

from asyncviz.dashboard.state.metrics_state import MetricsState
from asyncviz.dashboard.state.runtime_state import RuntimeState


def test_runtime_state_starts_idle() -> None:
    state = RuntimeState()
    assert state.status == "idle"
    assert state.uptime_seconds == 0.0


def test_runtime_state_lifecycle_transitions() -> None:
    state = RuntimeState()
    state.mark_started()
    assert state.status == "running"
    time.sleep(0.01)
    assert state.uptime_seconds > 0

    state.mark_stopped()
    assert state.status == "stopped"
    assert state.uptime_seconds > 0


def test_metrics_state_counters() -> None:
    metrics = MetricsState()
    snapshot = metrics.snapshot()
    assert snapshot.events_emitted == 0
    assert snapshot.websocket_messages_sent == 0

    metrics.inc_events(5)
    metrics.inc_ws_messages(2)
    snapshot = metrics.snapshot()

    assert snapshot.events_emitted == 5
    assert snapshot.websocket_messages_sent == 2
