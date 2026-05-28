from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app
from asyncviz.dashboard.health import (
    HEALTH_PROTOCOL_VERSION,
    CheckSeverity,
    DuplicateProbeError,
    HealthCheckRegistry,
    HealthCheckResult,
    HealthMetrics,
    HealthService,
    HealthStatus,
    aggregate_status,
    degraded,
    healthy,
    is_ready,
    starting,
    stopping,
    unavailable,
)
from asyncviz.dashboard.health.probes import (
    DEFAULT_PROBES,
    probe_runtime_lifecycle,
)

# ── Enum + aggregation primitives ─────────────────────────────────────────


def test_health_status_string_values_are_stable() -> None:
    assert HealthStatus.HEALTHY.value == "healthy"
    assert HealthStatus.DEGRADED.value == "degraded"
    assert HealthStatus.UNAVAILABLE.value == "unavailable"
    assert HealthStatus.STARTING.value == "starting"
    assert HealthStatus.STOPPING.value == "stopping"


@pytest.mark.parametrize(
    "statuses,expected",
    [
        ([], HealthStatus.HEALTHY),
        ([HealthStatus.HEALTHY], HealthStatus.HEALTHY),
        ([HealthStatus.HEALTHY, HealthStatus.STARTING], HealthStatus.STARTING),
        ([HealthStatus.HEALTHY, HealthStatus.STOPPING], HealthStatus.STOPPING),
        ([HealthStatus.HEALTHY, HealthStatus.DEGRADED], HealthStatus.DEGRADED),
        (
            [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.STARTING],
            HealthStatus.DEGRADED,
        ),
        ([HealthStatus.DEGRADED, HealthStatus.UNAVAILABLE], HealthStatus.UNAVAILABLE),
    ],
)
def test_aggregate_status_picks_worst(statuses: list[HealthStatus], expected: HealthStatus) -> None:
    assert aggregate_status(statuses) is expected


def test_is_ready_accepts_degraded_but_not_starting() -> None:
    assert is_ready(HealthStatus.HEALTHY) is True
    assert is_ready(HealthStatus.DEGRADED) is True
    assert is_ready(HealthStatus.STARTING) is False
    assert is_ready(HealthStatus.STOPPING) is False
    assert is_ready(HealthStatus.UNAVAILABLE) is False


# ── HealthCheckResult builders ────────────────────────────────────────────


def test_healthy_builder_defaults() -> None:
    result = healthy("probe")
    assert result.status is HealthStatus.HEALTHY
    assert result.severity is CheckSeverity.CRITICAL
    assert result.message == "ok"
    assert result.is_ok


def test_degraded_builder_defaults_info_severity() -> None:
    result = degraded("probe", "uh oh")
    assert result.status is HealthStatus.DEGRADED
    assert result.severity is CheckSeverity.INFO
    assert result.message == "uh oh"
    assert not result.is_ok


def test_unavailable_builder_defaults_critical_severity() -> None:
    result = unavailable("probe", "down")
    assert result.status is HealthStatus.UNAVAILABLE
    assert result.severity is CheckSeverity.CRITICAL


def test_starting_and_stopping_builders() -> None:
    s1 = starting("probe")
    s2 = stopping("probe")
    assert s1.status is HealthStatus.STARTING
    assert s2.status is HealthStatus.STOPPING


# ── HealthMetrics ─────────────────────────────────────────────────────────


def test_health_metrics_records_per_endpoint() -> None:
    metrics = HealthMetrics()
    metrics.record_liveness()
    metrics.record_readiness()
    metrics.record_full_check()
    metrics.record_runtime_diagnostics()
    metrics.record_evaluation(
        duration_ns=100_000, degraded=True, unavailable=False, probe_failures=1
    )
    snap = metrics.snapshot()
    assert snap.liveness_checks == 1
    assert snap.readiness_checks == 1
    assert snap.full_checks == 1
    assert snap.runtime_diagnostics_calls == 1
    assert snap.evaluations_total == 1
    assert snap.degraded_evaluations == 1
    assert snap.unavailable_evaluations == 0
    assert snap.probe_failures == 1
    assert snap.last_evaluation_ns == 100_000
    assert snap.average_evaluation_ns == 100_000


def test_health_metrics_reset_clears() -> None:
    metrics = HealthMetrics()
    metrics.record_liveness()
    metrics.reset()
    assert metrics.snapshot().liveness_checks == 0


# ── HealthCheckRegistry ───────────────────────────────────────────────────


def test_registry_registers_and_runs_probes() -> None:
    registry = HealthCheckRegistry()

    def my_probe(_state) -> HealthCheckResult:
        return healthy("my_probe")

    registry.register("my_probe", my_probe)
    assert "my_probe" in registry
    assert len(registry) == 1
    results, failures = registry.run(None)  # state unused by my_probe
    assert failures == 0
    assert len(results) == 1
    assert results[0].name == "my_probe"
    # Latency stamped by the registry, not the probe.
    assert results[0].latency_ns >= 0


def test_registry_rejects_duplicate_names() -> None:
    registry = HealthCheckRegistry()
    registry.register("p", lambda _s: healthy("p"))
    with pytest.raises(DuplicateProbeError):
        registry.register("p", lambda _s: healthy("p"))


def test_registry_replace_overwrites() -> None:
    registry = HealthCheckRegistry()
    registry.register("p", lambda _s: healthy("p"))
    registry.replace("p", lambda _s: degraded("p", "now degraded"))
    results, _ = registry.run(None)
    assert results[0].status is HealthStatus.DEGRADED


def test_registry_catches_probe_exceptions() -> None:
    """Raises become synthetic UNAVAILABLE results, not propagating exceptions."""
    registry = HealthCheckRegistry()

    def broken(_state):
        raise RuntimeError("kaboom")

    registry.register("broken", broken)
    results, failures = registry.run(None)
    assert failures == 1
    assert len(results) == 1
    assert results[0].status is HealthStatus.UNAVAILABLE
    assert "kaboom" in results[0].message
    assert results[0].details["exception_type"] == "RuntimeError"


def test_registry_filters_by_name() -> None:
    registry = HealthCheckRegistry()
    registry.register("a", lambda _s: healthy("a"))
    registry.register("b", lambda _s: healthy("b"))
    results, _ = registry.run(None, names=["a"])
    assert [r.name for r in results] == ["a"]


def test_registry_preserves_insertion_order() -> None:
    registry = HealthCheckRegistry()
    for name in ("alpha", "bravo", "charlie"):
        registry.register(name, lambda _s, n=name: healthy(n))
    assert registry.names() == ["alpha", "bravo", "charlie"]
    results, _ = registry.run(None)
    assert [r.name for r in results] == ["alpha", "bravo", "charlie"]


# ── Lifecycle probe maps RuntimeState → HealthStatus ──────────────────────


@pytest.fixture
def app():
    return create_app(AsyncVizConfig(frontend_mode="api-only"))


def test_runtime_lifecycle_probe_starting_before_lifespan(app) -> None:
    # ``create_app`` builds the runtime but the lifespan hasn't been
    # entered, so :class:`RuntimeState` is still ``idle``.
    result = probe_runtime_lifecycle(app.state.backend)
    assert result.status is HealthStatus.STARTING


def test_runtime_lifecycle_probe_running_inside_lifespan(app) -> None:
    with TestClient(app):
        result = probe_runtime_lifecycle(app.state.backend)
    # After the with-block, the lifespan exits and marks stopped.
    assert result.status is HealthStatus.HEALTHY


def test_runtime_lifecycle_probe_stopping_after_lifespan(app) -> None:
    with TestClient(app):
        pass
    result = probe_runtime_lifecycle(app.state.backend)
    assert result.status is HealthStatus.STOPPING


# ── HealthService.evaluate end-to-end ─────────────────────────────────────


def test_health_service_registers_every_default_probe(app) -> None:
    service = HealthService(state=app.state.backend)
    names = service.registry.names()
    assert set(names) == {name for name, _ in DEFAULT_PROBES}


def test_health_service_does_not_register_defaults_when_disabled(app) -> None:
    service = HealthService(state=app.state.backend, register_defaults=False)
    assert len(service.registry) == 0


def test_health_service_liveness_does_not_run_probes(app) -> None:
    service = HealthService(state=app.state.backend)
    before = service.metrics_snapshot().evaluations_total
    snap = service.liveness()
    after = service.metrics_snapshot().evaluations_total
    # Liveness doesn't run probes — evaluations_total must not advance.
    assert after == before
    assert snap.status is HealthStatus.HEALTHY
    assert snap.process_uptime_seconds >= 0.0


def test_health_service_full_check_runs_every_probe(app) -> None:
    with TestClient(app):
        service = app.state.health_service
        snap = service.evaluate()
        assert len(snap.checks) == len(DEFAULT_PROBES)
        # All defaults are HEALTHY inside the lifespan.
        assert snap.status is HealthStatus.HEALTHY
        assert snap.summary["healthy"] == len(DEFAULT_PROBES)
        assert snap.summary["checks_total"] == len(DEFAULT_PROBES)
        # Each probe carries a stamped latency.
        for check in snap.checks:
            assert check.latency_ns >= 0


def test_health_service_readiness_filters_to_critical(app) -> None:
    with TestClient(app):
        service = app.state.health_service
        snap = service.readiness()
        assert all(c.severity is CheckSeverity.CRITICAL for c in snap.critical_checks)
        assert snap.status is HealthStatus.HEALTHY


def test_health_service_diagnostics_includes_subsystem_counters(app) -> None:
    with TestClient(app):
        service = app.state.health_service
        snap = service.runtime_diagnostics()
        assert snap.status is HealthStatus.HEALTHY
        # Counters present and non-negative.
        for field_name in (
            "tasks_total",
            "queue_depth",
            "queue_capacity",
            "replay_frame_count",
            "websocket_active_sessions",
            "streaming_broadcast_failures",
            "warnings_active",
        ):
            assert getattr(snap, field_name) >= 0
        # Health checks embedded.
        assert len(snap.checks) == len(DEFAULT_PROBES)


def test_health_service_records_probe_failures(app) -> None:
    """Inject a misbehaving probe and assert the service surfaces it."""
    service = HealthService(state=app.state.backend, register_defaults=False)

    def broken(_state):
        raise RuntimeError("kaboom")

    service.registry.register("broken", broken)
    snap = service.evaluate()
    assert snap.status is HealthStatus.UNAVAILABLE
    metrics = service.metrics_snapshot()
    assert metrics.probe_failures >= 1


# ── HTTP endpoints ────────────────────────────────────────────────────────


def test_health_endpoint_returns_healthy_inside_lifespan(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["protocol_version"] == HEALTH_PROTOCOL_VERSION
        assert isinstance(body["checks"], list)
        assert body["summary"]["checks_total"] == len(DEFAULT_PROBES)


def test_health_live_endpoint_is_always_200(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["process_uptime_seconds"] >= 0.0


def test_health_ready_returns_200_when_healthy(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert isinstance(body["critical_checks"], list)


def test_health_ready_returns_503_when_unavailable(app) -> None:
    """Swap a critical probe to UNAVAILABLE and assert readiness fails with 503."""
    with TestClient(app) as client:
        app.state.health_service.registry.replace(
            "state_store",
            lambda _state: unavailable("state_store", "forced for test"),
        )
        response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "unavailable"


def test_health_ready_returns_200_when_degraded(app) -> None:
    """DEGRADED is still 200 — k8s shouldn't pull a pod for cosmetic problems."""
    with TestClient(app) as client:
        app.state.health_service.registry.replace(
            "warning_manager",
            lambda _state: degraded("warning_manager", "test degradation"),
        )
        response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] in {"healthy", "degraded"}


def test_health_runtime_endpoint_shape(app) -> None:
    with TestClient(app) as client:
        response = client.get("/api/health/runtime")
    assert response.status_code == 200
    body = response.json()
    for key in (
        "status",
        "tasks_total",
        "queue_depth",
        "replay_frame_count",
        "websocket_active_sessions",
        "streaming_running",
        "warnings_active",
        "summary",
        "checks",
    ):
        assert key in body


def test_health_metrics_endpoint_counts_evaluations(app) -> None:
    with TestClient(app) as client:
        client.get("/api/health")
        client.get("/api/health")
        client.get("/api/health/ready")
        client.get("/api/health/live")
        response = client.get("/api/health/metrics")
    assert response.status_code == 200
    data = response.json()
    # Two full evaluations + one readiness → 3 probe-run evaluations.
    assert data["full_checks"] >= 2
    assert data["readiness_checks"] >= 1
    assert data["liveness_checks"] >= 1
    assert data["evaluations_total"] >= 3


# ── Wiring ────────────────────────────────────────────────────────────────


def test_backend_state_exposes_health_service(app) -> None:
    assert app.state.backend.health_service is app.state.health_service


def test_health_service_runtime_id_matches_clock(app) -> None:
    with TestClient(app):
        snap = app.state.health_service.evaluate()
    assert snap.runtime_id == str(app.state.runtime_clock.runtime_id)
