from __future__ import annotations

import pytest

from asyncviz.configuration import (
    MonitoringOptions,
    NetworkOptions,
    RuntimeConfigurationError,
    RuntimeRecordingOptions,
    SecurityOptions,
    ValidationIssue,
    collect_issues,
    default_runtime_options,
    validate_options,
)


def test_default_options_validate_clean() -> None:
    validate_options(default_runtime_options())


def test_invalid_port_collected() -> None:
    options = default_runtime_options().with_overrides(network=NetworkOptions(port=70000))
    issues = collect_issues(options)
    assert any(i.field == "network.port" for i in issues)


def test_loopback_check_blocks_remote_host_without_opt_in() -> None:
    options = default_runtime_options().with_overrides(network=NetworkOptions(host="0.0.0.0"))
    issues = collect_issues(options)
    assert any(i.field == "network.host" for i in issues)


def test_loopback_check_clears_when_remote_allowed() -> None:
    options = default_runtime_options().with_overrides(
        network=NetworkOptions(host="0.0.0.0"),
        security=SecurityOptions(allow_remote_connections=True),
    )
    issues = collect_issues(options)
    assert not any(i.field == "network.host" for i in issues)


def test_inverted_lag_thresholds_rejected() -> None:
    options = default_runtime_options().with_overrides(
        monitoring=MonitoringOptions(
            lag_warning_ms=500.0,
            lag_critical_ms=100.0,
            lag_freeze_ms=50.0,
        ),
    )
    issues = collect_issues(options)
    assert any("warning ≤ critical ≤ freeze" in i.message for i in issues)


def test_recording_enabled_without_path_rejected() -> None:
    options = default_runtime_options().with_overrides(
        recording=RuntimeRecordingOptions(enabled=True),
    )
    issues = collect_issues(options)
    assert any(i.field == "recording.output_path" for i in issues)


def test_validate_options_raises_with_all_issues() -> None:
    options = default_runtime_options().with_overrides(network=NetworkOptions(host="", port=0))
    with pytest.raises(RuntimeConfigurationError) as exc:
        validate_options(options)
    assert len(exc.value.issues) >= 2
    assert any(isinstance(issue, ValidationIssue) for issue in exc.value.issues)
