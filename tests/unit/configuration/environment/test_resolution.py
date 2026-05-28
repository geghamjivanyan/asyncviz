from __future__ import annotations

from pathlib import Path

from asyncviz.configuration import (
    OptionSource,
    ProvenanceMap,
    default_runtime_options,
)
from asyncviz.configuration.environment import load_and_apply


def test_load_and_apply_overrides_options() -> None:
    options = default_runtime_options()
    result = load_and_apply(
        options,
        {
            "ASYNCVIZ_PORT": "9100",
            "ASYNCVIZ_LAG_FREEZE_MS": "750ms",
            "ASYNCVIZ_RECORDING_OUTPUT": "/tmp/x.avz",
        },
    )
    assert result.options.network.port == 9100
    assert result.options.monitoring.lag_freeze_ms == 750.0
    assert result.options.recording.enabled is True
    assert str(result.options.recording.output_path) == "/tmp/x.avz"


def test_load_and_apply_records_provenance() -> None:
    options = default_runtime_options()
    provenance = ProvenanceMap()
    load_and_apply(options, {"ASYNCVIZ_PORT": "9100"}, provenance=provenance)
    entry = provenance.get("network.port")
    assert entry is not None
    assert entry.source == OptionSource.ENVIRONMENT
    assert entry.value == 9100
    assert entry.raw_text == "9100"


def test_no_browser_env_forces_never_policy() -> None:
    options = default_runtime_options()
    result = load_and_apply(options, {"ASYNCVIZ_NO_BROWSER": "1"})
    assert result.options.browser.policy == "never"


def test_no_browser_false_leaves_policy_untouched() -> None:
    options = default_runtime_options()
    result = load_and_apply(options, {"ASYNCVIZ_NO_BROWSER": "false"})
    assert result.options.browser.policy == "auto"  # default


def test_exclude_events_parsed_into_tuple() -> None:
    options = default_runtime_options()
    result = load_and_apply(
        options,
        {"ASYNCVIZ_RECORDING_EXCLUDE_EVENTS": "asyncio.task.created, asyncio.task.completed"},
    )
    assert result.options.recording.exclude_event_types == (
        "asyncio.task.created",
        "asyncio.task.completed",
    )


def test_invalid_value_does_not_corrupt_options() -> None:
    options = default_runtime_options()
    result = load_and_apply(options, {"ASYNCVIZ_PORT": "not-a-number"})
    assert result.applied_count == 0
    assert result.failed_count == 1
    assert result.options.network.port == options.network.port  # untouched


def test_recording_output_uses_pathlib() -> None:
    options = default_runtime_options()
    result = load_and_apply(options, {"ASYNCVIZ_RECORDING_OUTPUT": "/tmp/x.avz"})
    assert isinstance(result.options.recording.output_path, Path)
