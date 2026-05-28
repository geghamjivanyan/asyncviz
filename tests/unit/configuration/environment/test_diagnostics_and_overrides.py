from __future__ import annotations

from asyncviz.configuration.environment import (
    EnvironmentConfigurationLoader,
    build_environment_diagnostics,
    clear_environment_trace,
    load_with_overrides,
    overrides_to_env,
    record_environment_trace,
    reset_environment_metrics,
    set_environment_trace_enabled,
    validate_loaded,
)


def setup_function(_fn: object) -> None:
    reset_environment_metrics()
    clear_environment_trace()
    set_environment_trace_enabled(False)


def test_overrides_to_env_normalizes_keys() -> None:
    out = overrides_to_env({"port": "9100", "log-level": "INFO"})
    assert out == {"ASYNCVIZ_PORT": "9100", "ASYNCVIZ_LOG_LEVEL": "INFO"}


def test_load_with_overrides_wins_over_environ() -> None:
    result = load_with_overrides(
        {"ASYNCVIZ_PORT": "9000"},
        overrides={"port": "9999"},
    )
    success_by_target = {item.spec.target: item.outcome.value for item in result.successes}
    assert success_by_target["network.port"] == 9999


def test_diagnostics_snapshot_carries_loader_summary() -> None:
    result = EnvironmentConfigurationLoader().load({"ASYNCVIZ_PORT": "9100"})
    snap = build_environment_diagnostics(result, validate_loaded(result.loaded))
    assert snap.loader_result["parsed_count"] == 1
    assert snap.validation.ok is True
    payload = snap.to_dict()
    assert payload["loader_result"]["parsed_count"] == 1
    assert payload["validation"]["ok"] is True


def test_trace_ring_records_events_when_enabled() -> None:
    set_environment_trace_enabled(True)
    record_environment_trace("load-start", "test")
    record_environment_trace("key-parsed", "ASYNCVIZ_PORT")
    snap = build_environment_diagnostics(
        EnvironmentConfigurationLoader().load({}),
        validate_loaded(()),
    )
    assert snap.trace_enabled is True
    kinds = [entry.kind for entry in snap.recent_trace]
    assert "load-start" in kinds
    assert "key-parsed" in kinds


def test_trace_ring_silent_when_disabled() -> None:
    record_environment_trace("load-start", "x")  # no-op
    snap = build_environment_diagnostics(
        EnvironmentConfigurationLoader().load({}),
        validate_loaded(()),
    )
    assert snap.trace_enabled is False
    assert snap.recent_trace == ()
