import pytest

from asyncviz.config import AsyncVizConfig


def test_defaults() -> None:
    config = AsyncVizConfig()
    assert config.host == "127.0.0.1"
    assert config.port == 8877
    assert config.open_browser is True
    assert config.debug is False


def test_dashboard_url() -> None:
    config = AsyncVizConfig(host="0.0.0.0", port=1234)
    assert config.dashboard_url == "http://0.0.0.0:1234"


def test_config_is_frozen() -> None:
    config = AsyncVizConfig()
    with pytest.raises((AttributeError, TypeError)):
        config.port = 9999  # type: ignore[misc]
