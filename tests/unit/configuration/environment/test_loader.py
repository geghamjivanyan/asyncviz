from __future__ import annotations

from asyncviz.configuration.environment.environment_loader import (
    EnvironmentConfigurationLoader,
)
from asyncviz.configuration.environment.environment_mapping import (
    CORE_ENV_VAR_SPECS,
)


def test_loader_parses_every_known_var() -> None:
    env = {
        "ASYNCVIZ_PORT": "9100",
        "ASYNCVIZ_LOG_LEVEL": "INFO",
        "ASYNCVIZ_LAG_WARNING_MS": "75ms",
    }
    result = EnvironmentConfigurationLoader().load(env)
    assert result.parsed.parsed_count == 3
    assert result.parsed.failed_count == 0


def test_loader_skips_unknown_vars() -> None:
    env = {"ASYNCVIZ_NOT_KNOWN": "boom"}
    result = EnvironmentConfigurationLoader().load(env)
    assert result.parsed.parsed_count == 0
    # Every spec we did know about ends up in skipped_count.
    assert result.parsed.skipped_count == len(CORE_ENV_VAR_SPECS)


def test_loader_records_parse_failures() -> None:
    env = {"ASYNCVIZ_PORT": "not-a-number"}
    result = EnvironmentConfigurationLoader().load(env)
    assert result.parsed.failed_count == 1
    assert result.failures[0].spec.target == "network.port"


def test_loader_rejects_oversize_values() -> None:
    env = {"ASYNCVIZ_PORT": "1" * (20 * 1024)}
    result = EnvironmentConfigurationLoader(max_value_bytes=128).load(env)
    assert result.parsed.failed_count == 1
    assert "exceeds max size" in result.parsed.diagnostics[0].message


def test_loader_ignores_blank_values() -> None:
    env = {"ASYNCVIZ_LOG_LEVEL": "  "}
    result = EnvironmentConfigurationLoader().load(env)
    assert result.parsed.parsed_count == 0
    assert result.parsed.failed_count == 0


def test_loader_walks_aliases_left_to_right() -> None:
    # No alias today, but the helper exposes the protocol.
    env = {"ASYNCVIZ_PORT": "9100"}
    result = EnvironmentConfigurationLoader().load(env)
    success = next(iter(result.successes))
    assert success.env_name == "ASYNCVIZ_PORT"
