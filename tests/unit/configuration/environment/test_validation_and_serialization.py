from __future__ import annotations

from asyncviz.configuration import default_runtime_options, resolve_options
from asyncviz.configuration.environment import (
    EnvironmentConfigurationLoader,
    export_options_to_env,
    loader_result_to_dict,
    validate_loaded,
)


def test_validate_loaded_clean_when_values_in_range() -> None:
    result = EnvironmentConfigurationLoader().load({"ASYNCVIZ_PORT": "9100"})
    report = validate_loaded(result.loaded)
    assert report.ok


def test_validate_loaded_rejects_out_of_range_port() -> None:
    result = EnvironmentConfigurationLoader().load({"ASYNCVIZ_PORT": "70000"})
    report = validate_loaded(result.loaded)
    assert not report.ok
    assert any("port" in issue.message for issue in report.issues)


def test_validate_loaded_rejects_negative_duration() -> None:
    result = EnvironmentConfigurationLoader().load({"ASYNCVIZ_LAG_WARNING_MS": "-50ms"})
    report = validate_loaded(result.loaded)
    assert not report.ok


def test_loader_result_to_dict_is_json_safe() -> None:
    import json

    result = EnvironmentConfigurationLoader().load(
        {"ASYNCVIZ_PORT": "9100", "ASYNCVIZ_NOT_A_NUMBER": "x"},
    )
    payload = loader_result_to_dict(result)
    json.dumps(payload)  # round-trip
    assert payload["parsed_count"] == 1
    assert len(payload["successes"]) == 1


def test_export_options_to_env_round_trip() -> None:
    resolved = resolve_options(
        environ={"ASYNCVIZ_PORT": "9100", "ASYNCVIZ_BROWSER": "always"},
    )
    exported = export_options_to_env(resolved.options)
    assert exported["ASYNCVIZ_PORT"] == "9100"
    assert exported["ASYNCVIZ_BROWSER"] == "always"
    # Default-valued options stay out of the export.
    assert "ASYNCVIZ_HEARTBEAT_INTERVAL" not in exported


def test_export_options_to_env_emits_zero_for_unset_defaults() -> None:
    options = default_runtime_options()
    exported = export_options_to_env(options)
    assert exported == {}
