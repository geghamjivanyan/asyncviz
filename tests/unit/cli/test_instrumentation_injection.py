from __future__ import annotations

import sys

from asyncviz.cli.configuration import RunCliConfig, TargetSpec
from asyncviz.cli.runtime.instrumentation_injection import (
    BOOTSTRAP_MODULE,
    build_bootstrap_command,
)


def _config(**overrides) -> RunCliConfig:  # type: ignore[no-untyped-def]
    return RunCliConfig(
        target=TargetSpec(kind="module", value="json", argv=("json",)),
        **overrides,
    )


def test_build_bootstrap_command_uses_sys_executable_by_default() -> None:
    argv = build_bootstrap_command(_config())
    assert argv == [sys.executable, "-m", BOOTSTRAP_MODULE]


def test_build_bootstrap_command_respects_python_override() -> None:
    argv = build_bootstrap_command(_config(python_executable="python3.13"))
    assert argv == ["python3.13", "-m", BOOTSTRAP_MODULE]


def test_build_bootstrap_command_keeps_absolute_python_override() -> None:
    override = "/opt/python3.13/bin/python"
    argv = build_bootstrap_command(_config(python_executable=override))
    assert argv[0] == override
