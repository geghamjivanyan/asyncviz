from __future__ import annotations

import pytest

from asyncviz.configuration import (
    OptionSource,
    ResolvedOptions,
    default_runtime_options,
    resolve_options,
)


def test_resolve_options_returns_defaults_when_no_inputs() -> None:
    resolved = resolve_options()
    assert isinstance(resolved, ResolvedOptions)
    assert resolved.options == default_runtime_options()
    assert resolved.profile_name is None


def test_profile_seeds_options() -> None:
    resolved = resolve_options(profile="dev")
    assert resolved.profile_name == "dev"
    assert resolved.options.dashboard.debug is True
    assert resolved.options.browser.policy == "auto"
    # Provenance should mark these as PROFILE-sourced.
    assert resolved.provenance.source_for("dashboard.debug") == OptionSource.PROFILE


def test_environment_overrides_profile() -> None:
    resolved = resolve_options(
        profile="dev",
        environ={"ASYNCVIZ_LOG_LEVEL": "WARNING", "ASYNCVIZ_PORT": "9000"},
    )
    assert resolved.options.dashboard.log_level == "WARNING"
    assert resolved.options.network.port == 9000
    assert resolved.provenance.source_for("network.port") == OptionSource.ENVIRONMENT
    assert resolved.provenance.source_for("dashboard.log_level") == OptionSource.ENVIRONMENT


def test_cli_overrides_environment() -> None:
    resolved = resolve_options(
        environ={"ASYNCVIZ_PORT": "9000"},
        cli_overrides={"port": 8000, "browser": "always"},
    )
    assert resolved.options.network.port == 8000
    assert resolved.options.browser.policy == "always"
    assert resolved.provenance.source_for("network.port") == OptionSource.CLI
    assert resolved.provenance.source_for("browser.policy") == OptionSource.CLI


def test_api_kwargs_take_precedence_over_env() -> None:
    resolved = resolve_options(
        environ={"ASYNCVIZ_HOST": "10.0.0.1"},
        api_overrides={"host": "172.16.0.1"},
    )
    assert resolved.options.network.host == "172.16.0.1"
    assert resolved.provenance.source_for("network.host") == OptionSource.API_KWARGS


def test_cli_overrides_api_kwargs() -> None:
    resolved = resolve_options(
        api_overrides={"port": 7000},
        cli_overrides={"port": 8000},
    )
    assert resolved.options.network.port == 8000
    assert resolved.provenance.source_for("network.port") == OptionSource.CLI


def test_unknown_profile_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        resolve_options(profile="nope")


def test_no_browser_env_forces_never_policy() -> None:
    resolved = resolve_options(environ={"ASYNCVIZ_NO_BROWSER": "1"})
    assert resolved.options.browser.policy == "never"


def test_open_browser_api_kwarg_maps_to_policy() -> None:
    resolved = resolve_options(api_overrides={"open_browser": False})
    assert resolved.options.browser.policy == "never"
    resolved = resolve_options(api_overrides={"open_browser": True})
    assert resolved.options.browser.policy == "auto"


def test_recording_output_env_enables_recording() -> None:
    resolved = resolve_options(environ={"ASYNCVIZ_RECORDING_OUTPUT": "/tmp/x.avz"})
    assert resolved.options.recording.enabled is True
    assert str(resolved.options.recording.output_path) == "/tmp/x.avz"
