"""Integration tests that spawn ``python -m asyncviz run`` for real.

These tests are intentionally lightweight — they verify the
end-to-end shape of the CLI without driving a full uvicorn lifecycle
on every assertion. The dashboard *is* started inside the subprocess
(that's the whole point of the CLI), so each test uses a unique port
to avoid binding collisions when the suite runs in parallel.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_TARGET_OK = """\
import asyncio
import os
import sys

async def main():
    print("ASYNCVIZ_TEST_OK")
    print("ARGV", " ".join(sys.argv[1:]))
    print("HOST", os.environ.get("ASYNCVIZ_CLI_DASHBOARD_HOST", ""))
    print("PORT", os.environ.get("ASYNCVIZ_CLI_DASHBOARD_PORT", ""))
    await asyncio.sleep(0.01)

asyncio.run(main())
"""

_TARGET_FAIL = """\
import sys
sys.exit(7)
"""

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    # Make sure the child subprocess of the test (which is itself a
    # subprocess of pytest) can find the repo. We use the parent
    # process's PYTHONPATH so editable installs keep working.
    env.setdefault("ASYNCVIZ_NO_BROWSER", "1")
    return env


def _run_cli(*args: str, port: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "asyncviz",
            "run",
            "--port",
            str(port),
            "--browser",
            "never",
            "--quiet",
            *args,
        ],
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=str(_REPO_ROOT),
        timeout=30,
    )


@pytest.mark.integration
def test_run_executes_script_and_propagates_argv(tmp_path: Path) -> None:
    script = tmp_path / "ok.py"
    script.write_text(_TARGET_OK, encoding="utf-8")
    result = _run_cli(str(script), "--", "--user", "value", port=8951)
    assert result.returncode == 0, result.stderr
    assert "ASYNCVIZ_TEST_OK" in result.stdout
    assert "ARGV --user value" in result.stdout
    assert "HOST 127.0.0.1" in result.stdout
    assert "PORT 8951" in result.stdout


@pytest.mark.integration
def test_run_returns_subprocess_exit_code_on_target_failure(tmp_path: Path) -> None:
    script = tmp_path / "fail.py"
    script.write_text(_TARGET_FAIL, encoding="utf-8")
    result = _run_cli(str(script), port=8952)
    # The CLI translates target non-zero into ExitCode.SUBPROCESS_CRASHED (13).
    assert result.returncode == 13, result.stderr


@pytest.mark.integration
def test_run_with_no_dashboard_still_executes_script(tmp_path: Path) -> None:
    script = tmp_path / "ok.py"
    script.write_text(_TARGET_OK, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "asyncviz",
            "run",
            "--port",
            "8953",
            "--browser",
            "never",
            "--no-dashboard",
            "--no-instrumentation",
            "--quiet",
            str(script),
        ],
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=str(_REPO_ROOT),
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "ASYNCVIZ_TEST_OK" in result.stdout


@pytest.mark.integration
def test_version_command_prints_version() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "asyncviz", "version"],
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=str(_REPO_ROOT),
        timeout=10,
    )
    assert result.returncode == 0
    assert "asyncviz " in result.stdout


@pytest.mark.integration
def test_doctor_command_succeeds() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "asyncviz", "doctor"],
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=str(_REPO_ROOT),
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    # Doctor writes to stderr (status lines); the report header is there.
    assert "AsyncViz Doctor" in result.stderr


@pytest.mark.integration
def test_run_rejects_missing_script() -> None:
    result = _run_cli("/nonexistent/path/does/not/exist.py", port=8954)
    # Should fail with ExitCode.CONFIGURATION_ERROR (3).
    assert result.returncode == 3, result.stderr
    assert "script not found" in result.stderr


@pytest.mark.integration
def test_run_help_lists_subcommands() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "asyncviz", "--help"],
        capture_output=True,
        text=True,
        env=_cli_env(),
        cwd=str(_REPO_ROOT),
        timeout=10,
    )
    assert result.returncode == 0
    assert "run " in result.stdout
    assert "doctor " in result.stdout
    assert "version " in result.stdout
