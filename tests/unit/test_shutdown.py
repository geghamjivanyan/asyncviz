from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app
from asyncviz.runtime.shutdown import (
    SHUTDOWN_PROTOCOL_VERSION,
    PhaseTiming,
    RuntimeShutdownCoordinator,
    ShutdownAlreadyRunningError,
    ShutdownMetrics,
    ShutdownNotCompletedError,
    ShutdownPhase,
    ShutdownReport,
    ShutdownTimeouts,
    is_in_progress,
    is_terminal,
    phase_index,
)

# ── Phase enum + helpers ──────────────────────────────────────────────────


def test_shutdown_phase_values_are_stable() -> None:
    assert ShutdownPhase.IDLE.value == "idle"
    assert ShutdownPhase.DRAINING.value == "draining"
    assert ShutdownPhase.FINALIZING.value == "finalizing"
    assert ShutdownPhase.STOPPING.value == "stopping"
    assert ShutdownPhase.STOPPED.value == "stopped"
    assert ShutdownPhase.FAILED.value == "failed"


def test_phase_index_is_monotonic_through_happy_path() -> None:
    happy_path = [
        ShutdownPhase.IDLE,
        ShutdownPhase.DRAINING,
        ShutdownPhase.FINALIZING,
        ShutdownPhase.STOPPING,
        ShutdownPhase.STOPPED,
    ]
    indices = [phase_index(p) for p in happy_path]
    assert indices == sorted(indices)


def test_is_terminal_and_in_progress() -> None:
    assert is_terminal(ShutdownPhase.STOPPED)
    assert is_terminal(ShutdownPhase.FAILED)
    assert not is_terminal(ShutdownPhase.IDLE)
    assert not is_terminal(ShutdownPhase.DRAINING)
    assert is_in_progress(ShutdownPhase.DRAINING)
    assert is_in_progress(ShutdownPhase.FINALIZING)
    assert is_in_progress(ShutdownPhase.STOPPING)
    assert not is_in_progress(ShutdownPhase.IDLE)
    assert not is_in_progress(ShutdownPhase.STOPPED)


# ── Timeouts ──────────────────────────────────────────────────────────────


def test_default_timeouts_are_bounded() -> None:
    t = ShutdownTimeouts()
    assert t.notification_window_seconds > 0
    assert t.drain_seconds > 0
    assert t.finalize_seconds > 0
    assert t.stop_seconds > 0
    assert t.total_seconds is not None and t.total_seconds > 0


def test_timeouts_can_disable_total_budget() -> None:
    t = ShutdownTimeouts(total_seconds=None)
    assert t.total_seconds is None


# ── ShutdownMetrics ───────────────────────────────────────────────────────


def test_metrics_records_request_and_completion() -> None:
    metrics = ShutdownMetrics()
    metrics.record_request()
    metrics.set_phase(ShutdownPhase.DRAINING)
    snap_mid = metrics.snapshot()
    assert snap_mid.shutdowns_requested == 1
    assert snap_mid.current_phase is ShutdownPhase.DRAINING
    report = ShutdownReport(
        final_phase=ShutdownPhase.STOPPED,
        reason="test",
        triggered_at_monotonic_ns=100,
        finished_at_monotonic_ns=200,
        total_duration_ns=100,
        timeouts_total=1,
        forced_disconnects=2,
        forced_cancellations=3,
    )
    metrics.record_completion(report)
    snap = metrics.snapshot()
    assert snap.shutdowns_completed == 1
    assert snap.shutdowns_failed == 0
    assert snap.timeouts_total == 1
    assert snap.forced_disconnects == 2
    assert snap.forced_cancellations == 3
    assert snap.last_total_duration_ns == 100
    assert snap.max_total_duration_ns == 100


def test_metrics_distinguishes_failed_reports() -> None:
    metrics = ShutdownMetrics()
    report = ShutdownReport(
        final_phase=ShutdownPhase.FAILED,
        reason="kaboom",
        triggered_at_monotonic_ns=0,
        finished_at_monotonic_ns=10,
        total_duration_ns=10,
    )
    metrics.record_completion(report)
    snap = metrics.snapshot()
    assert snap.shutdowns_completed == 0
    assert snap.shutdowns_failed == 1


# ── Coordinator: happy-path through TestClient lifespan ───────────────────


@pytest.fixture
def app():
    return create_app(AsyncVizConfig(frontend_mode="api-only"))


def test_coordinator_is_wired_into_app(app) -> None:
    assert app.state.shutdown_coordinator is not None
    assert isinstance(app.state.shutdown_coordinator, RuntimeShutdownCoordinator)
    assert app.state.backend.shutdown_coordinator is app.state.shutdown_coordinator


def test_phase_is_idle_before_lifespan(app) -> None:
    assert app.state.shutdown_coordinator.phase is ShutdownPhase.IDLE
    assert app.state.shutdown_coordinator.is_requested is False
    assert app.state.shutdown_coordinator.is_completed is False


def test_phase_is_stopped_after_lifespan(app) -> None:
    coordinator = app.state.shutdown_coordinator
    with TestClient(app):
        # Inside the lifespan the runtime is up; coordinator is still idle.
        assert coordinator.phase is ShutdownPhase.IDLE
    # Exiting the with-block drives the lifespan finally → coordinator.run().
    assert coordinator.phase is ShutdownPhase.STOPPED
    assert coordinator.is_completed is True
    assert app.state.runtime_state.status == "stopped"


def test_report_available_after_terminal_phase(app) -> None:
    with TestClient(app):
        pass
    report = app.state.shutdown_coordinator.report()
    assert isinstance(report, ShutdownReport)
    assert report.final_phase is ShutdownPhase.STOPPED
    assert report.succeeded is True
    assert report.reason == "lifespan"
    assert report.total_duration_ns > 0
    # Every phase fired.
    phases = {pt.phase for pt in report.phase_timings}
    assert ShutdownPhase.DRAINING in phases
    assert ShutdownPhase.FINALIZING in phases
    assert ShutdownPhase.STOPPING in phases


def test_report_raises_before_terminal_phase(app) -> None:
    coordinator = app.state.shutdown_coordinator
    with pytest.raises(ShutdownNotCompletedError):
        coordinator.report()


def test_maybe_report_returns_none_before_terminal_phase(app) -> None:
    coordinator = app.state.shutdown_coordinator
    assert coordinator.maybe_report() is None
    with TestClient(app):
        pass
    assert coordinator.maybe_report() is not None


def test_request_shutdown_is_idempotent(app) -> None:
    coordinator = app.state.shutdown_coordinator
    coordinator.request_shutdown(reason="test-1")
    initial_phase = coordinator.phase
    coordinator.request_shutdown(reason="test-2")
    # Phase did not regress; reason was not overwritten.
    assert coordinator.phase is initial_phase
    # Run + verify reason captured the first call.
    asyncio.run(coordinator.run())
    report = coordinator.report()
    assert report.reason == "test-1"


def test_final_artifacts_are_captured(app) -> None:
    with TestClient(app):
        pass
    report = app.state.shutdown_coordinator.report()
    # Replay buffer + snapshot service both fired during finalize.
    assert report.checkpoint_id is not None
    assert report.snapshot_id is not None
    assert report.final_sequence is not None


def test_lifespan_runs_shutdown_only_once(app) -> None:
    """Calling ``run`` again after a terminal phase returns the cached report."""
    with TestClient(app):
        pass
    coordinator = app.state.shutdown_coordinator
    first = coordinator.report()
    second = asyncio.run(coordinator.run(reason="ignored"))
    # Same identity — coordinator short-circuits when already terminal.
    assert second is first


def test_phase_progress_is_monotonic_through_run(app) -> None:
    """Snapshot phase between ``run`` calls and assert ordering."""

    seen: list[ShutdownPhase] = []
    coordinator = app.state.shutdown_coordinator

    # Wrap the internal _set_phase to record transitions in order.
    original = coordinator._set_phase

    def tracking(phase):
        seen.append(phase)
        return original(phase)

    coordinator._set_phase = tracking  # type: ignore[method-assign]

    with TestClient(app):
        pass

    assert seen[0] is ShutdownPhase.DRAINING
    assert ShutdownPhase.FINALIZING in seen
    assert ShutdownPhase.STOPPING in seen
    assert seen[-1] is ShutdownPhase.STOPPED
    # Indices are monotonic (with the exception of the IDLE->DRAINING
    # set fired by request_shutdown before the run loop).
    indices = [phase_index(p) for p in seen]
    assert indices == sorted(indices)


# ── HTTP endpoints ────────────────────────────────────────────────────────


def test_shutdown_endpoint_reports_idle_inside_lifespan(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/runtime/shutdown")
    assert response.status_code == 200
    body = response.json()
    assert body["protocol_version"] == SHUTDOWN_PROTOCOL_VERSION
    assert body["phase"] == "idle"
    assert body["requested"] is False
    assert body["in_progress"] is False
    assert body["completed"] is False
    assert body["report"] is None


def test_shutdown_metrics_endpoint_shape(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/runtime/shutdown/metrics")
    assert response.status_code == 200
    data = response.json()
    for key in (
        "current_phase",
        "shutdowns_requested",
        "shutdowns_completed",
        "shutdowns_failed",
        "timeouts_total",
        "forced_disconnects",
        "forced_cancellations",
        "last_total_duration_ns",
        "max_total_duration_ns",
    ):
        assert key in data
    assert data["current_phase"] == "idle"


# ── Coordinator: concurrent run protection ───────────────────────────────


def test_concurrent_run_raises(app) -> None:
    """Two simultaneous ``run`` calls are rejected, not allowed to interleave."""
    coordinator = app.state.shutdown_coordinator

    # The shutdown sequence is microseconds on a clean runtime, so an
    # un-slowed ``task_a`` finishes before ``scenario`` resumes from
    # ``await asyncio.sleep(0)``. Inject a slow phase so the race
    # window is observable.
    original_drain = coordinator._drain_phase

    async def slow_drain() -> None:
        await asyncio.sleep(0.05)
        await original_drain()

    coordinator._drain_phase = slow_drain  # type: ignore[method-assign]

    async def scenario():
        task_a = asyncio.create_task(coordinator.run(reason="a"))
        # Yield until task_a is mid-run.
        await asyncio.sleep(0.01)
        with pytest.raises(ShutdownAlreadyRunningError):
            await coordinator.run(reason="b")
        await task_a

    asyncio.run(scenario())
    assert coordinator.phase is ShutdownPhase.STOPPED


# ── Cancellation attribution ──────────────────────────────────────────────


def test_cancellation_context_engages_during_run(app) -> None:
    """During the run, cancellation_context reports shutdown-in-progress."""
    coordinator = app.state.shutdown_coordinator
    ctx = app.state.patcher.cancellation_context

    flag_during_run: list[bool] = []

    async def scenario():
        # Patch the finalize phase to peek at the cancellation context.
        original = coordinator._capture_final_artifacts

        async def peek():
            flag_during_run.append(ctx.shutdown_in_progress)
            await original()

        coordinator._capture_final_artifacts = peek  # type: ignore[method-assign]
        await coordinator.run(reason="cancellation-test")

    asyncio.run(scenario())
    assert flag_during_run == [True]
    # After shutdown completes, the context is closed again.
    assert ctx.shutdown_in_progress is False


# ── PhaseTiming dataclass shape ───────────────────────────────────────────


def test_phase_timing_records_duration_and_timeout() -> None:
    pt = PhaseTiming(phase=ShutdownPhase.DRAINING, duration_ns=12_345, timed_out=False)
    assert pt.phase is ShutdownPhase.DRAINING
    assert pt.duration_ns == 12_345
    assert pt.timed_out is False
    # Frozen dataclasses raise FrozenInstanceError on attribute writes.
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        pt.duration_ns = 99  # type: ignore[misc]


# ── Total-budget timeout escalates to FAILED ──────────────────────────────


def test_total_budget_timeout_marks_failed(app) -> None:
    """Force a tiny total budget so the run aborts mid-flight."""
    coordinator = app.state.shutdown_coordinator
    # Replace the timeouts with a near-zero total budget.
    coordinator._timeouts = ShutdownTimeouts(
        notification_window_seconds=0.001,
        drain_seconds=0.001,
        finalize_seconds=0.001,
        stop_seconds=0.001,
        total_seconds=0.0001,  # effectively immediate
    )
    # Inject a slow drain so the budget actually trips.
    original = coordinator._notify_and_drain

    async def slow():
        await asyncio.sleep(0.5)
        await original()

    coordinator._notify_and_drain = slow  # type: ignore[method-assign]

    report = asyncio.run(coordinator.run(reason="forced-budget"))
    assert report.final_phase is ShutdownPhase.FAILED
    assert report.timeouts_total >= 1
    assert any("budget" in err for err in report.errors)


# ── Forced disconnect accounting ─────────────────────────────────────────


def test_forced_disconnect_counts_clients(app) -> None:
    """Inject fake clients into the manager and assert they are counted."""
    coordinator = app.state.shutdown_coordinator
    manager = app.state.websocket_manager

    class _FakeClient:
        """Stand-in for :class:`WebSocketClient` — must implement both
        ``send_text`` (so the drain-phase broadcast doesn't drop us)
        and ``close`` (so ``disconnect_all`` runs cleanly)."""

        def __init__(self, cid: str) -> None:
            self.id = cid

        async def send_text(self, text: str) -> None:
            pass

        async def close(self) -> None:
            pass

    manager._clients["a"] = _FakeClient("a")
    manager._clients["b"] = _FakeClient("b")
    assert manager.client_count == 2

    asyncio.run(coordinator.run(reason="forced-disconnect"))
    report = coordinator.report()
    assert report.forced_disconnects >= 2
    assert manager.client_count == 0
