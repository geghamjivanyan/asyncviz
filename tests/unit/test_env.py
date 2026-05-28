from pathlib import Path

import pytest

from asyncviz.config import AsyncVizConfig
from asyncviz.utils.env import load_dotenv, parse_bool, parse_int


def test_parse_bool_truthy() -> None:
    for value in ["1", "true", "True", "YES", "on", "y"]:
        assert parse_bool(value, default=False) is True


def test_parse_bool_falsy() -> None:
    for value in ["0", "false", "no", "off", "n"]:
        assert parse_bool(value, default=True) is False


def test_parse_bool_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_bool("maybe", default=False)


def test_parse_bool_default_when_none() -> None:
    assert parse_bool(None, default=True) is True
    assert parse_bool(None, default=False) is False


def test_parse_int_defaults_when_missing() -> None:
    assert parse_int(None, default=42) == 42
    assert parse_int("", default=42) == 42


def test_parse_int_returns_value() -> None:
    assert parse_int("8080", default=0) == 8080


def test_load_dotenv_populates_environ(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# comment\nASYNCVIZ_HOST=0.0.0.0\nASYNCVIZ_PORT="9000"\n'
        "ASYNCVIZ_DEBUG=true\nINVALID LINE\n"
    )
    monkeypatch.delenv("ASYNCVIZ_HOST", raising=False)
    monkeypatch.delenv("ASYNCVIZ_PORT", raising=False)
    monkeypatch.delenv("ASYNCVIZ_DEBUG", raising=False)

    count = load_dotenv(env_file)

    assert count == 3
    import os

    assert os.environ["ASYNCVIZ_HOST"] == "0.0.0.0"
    assert os.environ["ASYNCVIZ_PORT"] == "9000"
    assert os.environ["ASYNCVIZ_DEBUG"] == "true"


def test_load_dotenv_respects_existing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ASYNCVIZ_HOST=should-not-win\n")
    monkeypatch.setenv("ASYNCVIZ_HOST", "preset")

    load_dotenv(env_file)

    import os

    assert os.environ["ASYNCVIZ_HOST"] == "preset"


def test_load_dotenv_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("ASYNCVIZ_HOST=should-win\n")
    monkeypatch.setenv("ASYNCVIZ_HOST", "preset")

    load_dotenv(env_file, override=True)

    import os

    assert os.environ["ASYNCVIZ_HOST"] == "should-win"


def test_config_from_env_uses_defaults_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ["ASYNCVIZ_HOST", "ASYNCVIZ_PORT", "ASYNCVIZ_OPEN_BROWSER", "ASYNCVIZ_DEBUG"]:
        monkeypatch.delenv(key, raising=False)
    config = AsyncVizConfig.from_env()
    assert config == AsyncVizConfig()


def test_config_from_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASYNCVIZ_HOST", "0.0.0.0")
    monkeypatch.setenv("ASYNCVIZ_PORT", "9000")
    monkeypatch.setenv("ASYNCVIZ_OPEN_BROWSER", "false")
    monkeypatch.setenv("ASYNCVIZ_DEBUG", "true")

    config = AsyncVizConfig.from_env()

    assert config.host == "0.0.0.0"
    assert config.port == 9000
    assert config.open_browser is False
    assert config.debug is True
