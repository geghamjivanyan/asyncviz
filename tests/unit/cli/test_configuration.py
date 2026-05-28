from __future__ import annotations

from pathlib import Path

import pytest

from asyncviz.cli.configuration import (
    ConfigurationValidationError,
    RunCliConfig,
    TargetSpec,
    validate_run_config,
)


def _config(**overrides) -> RunCliConfig:  # type: ignore[no-untyped-def]
    defaults: dict[str, object] = {
        "target": TargetSpec(kind="module", value="json", argv=("json",)),
    }
    defaults.update(overrides)
    return RunCliConfig(**defaults)


def test_validate_run_config_accepts_module_target() -> None:
    validate_run_config(_config())


def test_validate_run_config_rejects_invalid_host() -> None:
    with pytest.raises(ConfigurationValidationError):
        validate_run_config(_config(host="bad host"))


@pytest.mark.parametrize("port", [0, 70000, -1])
def test_validate_run_config_rejects_invalid_port(port: int) -> None:
    with pytest.raises(ConfigurationValidationError):
        validate_run_config(_config(port=port))


def test_validate_run_config_rejects_missing_script(tmp_path: Path) -> None:
    bogus = tmp_path / "does-not-exist.py"
    with pytest.raises(ConfigurationValidationError):
        validate_run_config(
            _config(target=TargetSpec(kind="script", value=str(bogus), argv=(str(bogus),))),
        )


def test_validate_run_config_accepts_existing_script(tmp_path: Path) -> None:
    script = tmp_path / "ok.py"
    script.write_text("print('hi')\n")
    validate_run_config(
        _config(target=TargetSpec(kind="script", value=str(script), argv=(str(script),))),
    )


def test_validate_run_config_rejects_bad_module_name() -> None:
    with pytest.raises(ConfigurationValidationError):
        validate_run_config(
            _config(target=TargetSpec(kind="module", value="not a module!", argv=())),
        )


def test_validate_run_config_rejects_negative_timeout() -> None:
    with pytest.raises(ConfigurationValidationError):
        validate_run_config(_config(startup_timeout=-0.5))
    with pytest.raises(ConfigurationValidationError):
        validate_run_config(_config(shutdown_timeout=-1.0))


def test_validate_run_config_rejects_missing_cwd(tmp_path: Path) -> None:
    nowhere = tmp_path / "nope"
    with pytest.raises(ConfigurationValidationError):
        validate_run_config(_config(cwd=nowhere))


def test_validate_run_config_rejects_empty_env_key() -> None:
    with pytest.raises(ConfigurationValidationError):
        validate_run_config(_config(env_overrides=(("", "bar"),)))


def test_validate_run_config_rejects_python_empty_string() -> None:
    with pytest.raises(ConfigurationValidationError):
        validate_run_config(_config(python_executable="   "))


def test_run_cli_config_dashboard_url() -> None:
    cfg = _config(host="0.0.0.0", port=8888)
    assert cfg.dashboard_url == "http://0.0.0.0:8888"
