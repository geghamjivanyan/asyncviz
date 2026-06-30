from __future__ import annotations

import pytest

from asyncviz.bootstrap.config import resolve_config
from asyncviz.bootstrap.validation import ConfigError, validate_config
from asyncviz.config import DEFAULT_CORS_ALLOWED_ORIGINS, AsyncVizConfig


def test_resolve_uses_defaults_when_nothing_set() -> None:
    config = resolve_config(env={})
    assert config == AsyncVizConfig()


def test_resolve_env_overrides_defaults() -> None:
    config = resolve_config(
        env={
            "ASYNCVIZ_HOST": "0.0.0.0",
            "ASYNCVIZ_PORT": "9000",
            "ASYNCVIZ_OPEN_BROWSER": "false",
            "ASYNCVIZ_DEBUG": "true",
            "ASYNCVIZ_HEARTBEAT_INTERVAL": "0.5",
            "ASYNCVIZ_FRONTEND_MODE": "api-only",
            "ASYNCVIZ_LOG_LEVEL": "WARNING",
            "ASYNCVIZ_STARTUP_TIMEOUT": "2.5",
        }
    )

    assert config.host == "0.0.0.0"
    assert config.port == 9000
    assert config.open_browser is False
    assert config.debug is True
    assert config.heartbeat_interval == 0.5
    assert config.frontend_mode == "api-only"
    assert config.log_level == "WARNING"
    assert config.startup_timeout == 2.5


def test_resolve_kwargs_beat_env() -> None:
    config = resolve_config(
        env={"ASYNCVIZ_HOST": "0.0.0.0", "ASYNCVIZ_PORT": "9000"},
        host="10.0.0.1",
        port=12345,
    )
    assert config.host == "10.0.0.1"
    assert config.port == 12345


def test_resolve_explicit_false_overrides_env_true() -> None:
    config = resolve_config(
        env={"ASYNCVIZ_OPEN_BROWSER": "true"},
        open_browser=False,
    )
    assert config.open_browser is False


def test_effective_log_level_follows_debug() -> None:
    assert AsyncVizConfig().effective_log_level == "INFO"
    assert AsyncVizConfig(debug=True).effective_log_level == "DEBUG"
    assert AsyncVizConfig(log_level="WARNING").effective_log_level == "WARNING"


@pytest.mark.parametrize(
    "config",
    [
        AsyncVizConfig(port=0),
        AsyncVizConfig(port=70000),
        AsyncVizConfig(host=""),
        AsyncVizConfig(heartbeat_interval=0),
        AsyncVizConfig(heartbeat_interval=-1),
        AsyncVizConfig(startup_timeout=0),
    ],
)
def test_invalid_configs_rejected(config: AsyncVizConfig) -> None:
    with pytest.raises(ConfigError):
        validate_config(config)


def test_valid_config_passes() -> None:
    validate_config(AsyncVizConfig())


def test_cors_defaults_include_vite_dev_origins() -> None:
    # The Vite standalone workflow must work out of the box without
    # needing any env config — the documented dev origins on :5173
    # ship as defaults.
    config = AsyncVizConfig()
    assert "http://localhost:5173" in config.cors_allowed_origins
    assert "http://127.0.0.1:5173" in config.cors_allowed_origins
    assert config.cors_allowed_origins == DEFAULT_CORS_ALLOWED_ORIGINS


def test_cors_env_parses_comma_separated_origins() -> None:
    config = resolve_config(
        env={
            "ASYNCVIZ_CORS_ALLOWED_ORIGINS": (
                "http://app.example.com, https://admin.example.com,  http://localhost:5173"
            ),
        }
    )
    assert config.cors_allowed_origins == (
        "http://app.example.com",
        "https://admin.example.com",
        "http://localhost:5173",
    )


def test_cors_env_none_token_disables_cors() -> None:
    config = resolve_config(env={"ASYNCVIZ_CORS_ALLOWED_ORIGINS": "none"})
    assert config.cors_allowed_origins == ()


def test_cors_env_empty_string_falls_back_to_default() -> None:
    config = resolve_config(env={"ASYNCVIZ_CORS_ALLOWED_ORIGINS": ""})
    assert config.cors_allowed_origins == DEFAULT_CORS_ALLOWED_ORIGINS


def test_cors_kwarg_beats_env() -> None:
    config = resolve_config(
        env={"ASYNCVIZ_CORS_ALLOWED_ORIGINS": "http://env.example.com"},
        cors_allowed_origins=["http://kwarg.example.com"],
    )
    assert config.cors_allowed_origins == ("http://kwarg.example.com",)


def test_cors_wildcard_origin_round_trips() -> None:
    config = resolve_config(env={"ASYNCVIZ_CORS_ALLOWED_ORIGINS": "*"})
    assert config.cors_allowed_origins == ("*",)
