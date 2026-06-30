from __future__ import annotations

import pytest

from asyncviz.configuration.environment.environment_normalization import (
    normalize_env_key,
    strip_namespace,
)
from asyncviz.configuration.environment.environment_security import (
    REDACTED_VALUE,
    is_secret_key,
    redact_mapping,
    redact_value,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("port", "PORT"),
        ("dashboard-port", "DASHBOARD_PORT"),
        ("dashboard.port", "DASHBOARD_PORT"),
        ("  spaced key  ", "SPACED_KEY"),
    ],
)
def test_normalize_env_key_uppercases_and_normalizes_separators(
    raw: str,
    expected: str,
) -> None:
    assert normalize_env_key(raw) == expected


def test_normalize_env_key_prepends_namespace() -> None:
    assert normalize_env_key("port", namespace="ASYNCVIZ_") == "ASYNCVIZ_PORT"
    assert normalize_env_key("ASYNCVIZ_PORT", namespace="ASYNCVIZ_") == "ASYNCVIZ_PORT"


def test_strip_namespace_handles_present_and_absent() -> None:
    assert strip_namespace("ASYNCVIZ_PORT", "ASYNCVIZ_") == "PORT"
    assert strip_namespace("OTHER", "ASYNCVIZ_") == "OTHER"


@pytest.mark.parametrize(
    "key,expected",
    [
        ("AUTH_TOKEN", True),
        ("DATABASE_PASSWORD", True),
        ("API_SECRET", True),
        ("SECRET_KEY", True),
        ("ASYNCVIZ_PORT", False),
        ("", False),
    ],
)
def test_is_secret_key(key: str, expected: bool) -> None:
    assert is_secret_key(key) is expected


def test_redact_value_returns_sentinel_for_secrets() -> None:
    assert redact_value("AUTH_TOKEN", "abc123") == REDACTED_VALUE
    assert redact_value("ASYNCVIZ_PORT", "9000") == "9000"


def test_redact_mapping_filters_only_sensitive_keys() -> None:
    result = redact_mapping({"AUTH_TOKEN": "abc", "ASYNCVIZ_PORT": "9000"})
    assert result["AUTH_TOKEN"] == REDACTED_VALUE
    assert result["ASYNCVIZ_PORT"] == "9000"
