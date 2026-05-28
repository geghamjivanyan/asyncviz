from __future__ import annotations

import json

from asyncviz.cli.configuration import RunCliConfig, TargetSpec
from asyncviz.cli.runtime.bootstrap_entry import BOOTSTRAP_ENV_PREFIX
from asyncviz.cli.runtime.process_environment import build_subprocess_environment


def _config(**overrides) -> RunCliConfig:  # type: ignore[no-untyped-def]
    base: dict[str, object] = {
        "target": TargetSpec(kind="module", value="json", argv=("json", "arg")),
    }
    base.update(overrides)
    return RunCliConfig(**base)


def test_build_subprocess_environment_injects_bootstrap_vars() -> None:
    cfg = _config(host="127.0.0.1", port=9123, debug=True)
    env = build_subprocess_environment(cfg, base_env={})
    assert env[f"{BOOTSTRAP_ENV_PREFIX}TARGET_KIND"] == "module"
    assert env[f"{BOOTSTRAP_ENV_PREFIX}TARGET_VALUE"] == "json"
    assert env[f"{BOOTSTRAP_ENV_PREFIX}DASHBOARD_HOST"] == "127.0.0.1"
    assert env[f"{BOOTSTRAP_ENV_PREFIX}DASHBOARD_PORT"] == "9123"
    assert env[f"{BOOTSTRAP_ENV_PREFIX}DEBUG"] == "1"
    assert json.loads(env[f"{BOOTSTRAP_ENV_PREFIX}TARGET_ARGV_JSON"]) == ["json", "arg"]


def test_build_subprocess_environment_layers_overrides_last() -> None:
    cfg = _config(env_overrides=(("FOO", "USER_VALUE"),))
    env = build_subprocess_environment(cfg, base_env={"FOO": "from-shell"})
    assert env["FOO"] == "USER_VALUE"


def test_build_subprocess_environment_preserves_base_env() -> None:
    cfg = _config()
    env = build_subprocess_environment(cfg, base_env={"PATH": "/usr/local/bin"})
    assert env["PATH"] == "/usr/local/bin"


def test_build_subprocess_environment_sets_utf8_defaults() -> None:
    cfg = _config()
    env = build_subprocess_environment(cfg, base_env={})
    assert env["PYTHONIOENCODING"] == "utf-8"
    assert env["PYTHONUNBUFFERED"] == "1"


def test_build_subprocess_environment_no_dashboard_flag_propagates() -> None:
    cfg = _config(no_dashboard=True)
    env = build_subprocess_environment(cfg, base_env={})
    assert env[f"{BOOTSTRAP_ENV_PREFIX}START_DASHBOARD"] == "0"


def test_build_subprocess_environment_no_instrumentation_flag_propagates() -> None:
    cfg = _config(enable_instrumentation=False)
    env = build_subprocess_environment(cfg, base_env={})
    assert env[f"{BOOTSTRAP_ENV_PREFIX}ENABLE_INSTRUMENTATION"] == "0"
