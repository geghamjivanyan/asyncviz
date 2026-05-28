from __future__ import annotations

import pytest

from asyncviz.cli.parser import parse


def test_parse_run_with_script_and_argv() -> None:
    cmd, _ = parse(["run", "app.py", "--", "--flag", "value"])
    assert cmd.command == "run"
    assert cmd.run_config is not None
    target = cmd.run_config.target
    assert target.kind == "script"
    assert target.value == "app.py"
    assert target.argv == ("app.py", "--flag", "value")


def test_parse_run_with_module_and_no_extra_argv() -> None:
    cmd, _ = parse(["run", "-m", "pkg.module"])
    assert cmd.command == "run"
    assert cmd.run_config is not None
    target = cmd.run_config.target
    assert target.kind == "module"
    assert target.value == "pkg.module"
    assert target.argv == ("pkg.module",)


def test_parse_run_strips_double_dash_separator() -> None:
    cmd, _ = parse(["run", "-m", "pkg", "--", "extra"])
    assert cmd.run_config is not None
    assert cmd.run_config.target.argv == ("pkg", "extra")


def test_parse_run_dashboard_flags() -> None:
    cmd, _ = parse(
        [
            "run",
            "--host",
            "0.0.0.0",
            "--port",
            "9999",
            "--browser",
            "never",
            "--debug",
            "--no-instrumentation",
            "--quiet",
            "--",
            # Use a placeholder script path; validation runs at command
            # time, not at parse time, so missing-file is fine here.
            "app.py",
        ],
    )
    assert cmd.run_config is not None
    cfg = cmd.run_config
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9999
    assert cfg.browser == "never"
    assert cfg.debug is True
    assert cfg.enable_instrumentation is False
    assert cfg.quiet is True


def test_parse_run_env_overrides_keyvalue() -> None:
    cmd, _ = parse(["run", "-e", "FOO=bar", "-e", "BAZ=qux", "--", "app.py"])
    assert cmd.run_config is not None
    assert cmd.run_config.env_overrides == (("FOO", "bar"), ("BAZ", "qux"))


def test_parse_run_env_without_equals_exits() -> None:
    with pytest.raises(SystemExit):
        parse(["run", "-e", "NOEQ", "--", "app.py"])


def test_parse_no_command_exits_with_usage() -> None:
    with pytest.raises(SystemExit) as exc:
        parse([])
    assert exc.value.code == 2


def test_parse_version_command() -> None:
    cmd, _ = parse(["version"])
    assert cmd.command == "version"
    assert cmd.run_config is None


def test_parse_doctor_command_json_flag() -> None:
    cmd, args = parse(["doctor", "--json"])
    assert cmd.command == "doctor"
    assert args.emit_json is True


def test_parse_run_requires_target() -> None:
    with pytest.raises(SystemExit):
        parse(["run"])
