from __future__ import annotations

import platform

import pytest

from asyncviz.cli.browser.browser_detection import (
    detect_browser_availability,
)


def test_detect_browser_marks_explicit_opt_out() -> None:
    avail = detect_browser_availability({"ASYNCVIZ_NO_BROWSER": "1"})
    assert not avail.available
    assert avail.code == "explicit-opt-out"
    assert "ASYNCVIZ_NO_BROWSER" in avail.signals


def test_detect_browser_marks_policy_never_env() -> None:
    avail = detect_browser_availability({"ASYNCVIZ_BROWSER": "never"})
    assert not avail.available
    assert avail.code == "explicit-opt-out"


@pytest.mark.parametrize(
    "env_key",
    ["CI", "GITHUB_ACTIONS", "BUILDKITE", "GITLAB_CI", "CIRCLECI"],
)
def test_detect_browser_recognises_common_ci_signals(env_key: str) -> None:
    avail = detect_browser_availability({env_key: "1"})
    assert not avail.available
    assert avail.code == "ci"
    assert env_key in avail.signals


def test_detect_browser_marks_ssh_no_display() -> None:
    if platform.system() == "Darwin":
        pytest.skip("macOS SSH heuristic specifically allows the open")
    avail = detect_browser_availability({"SSH_CONNECTION": "1.2.3.4 22 5.6.7.8 22"})
    assert not avail.available
    assert avail.code == "ssh-no-display"


def test_detect_browser_returns_available_when_env_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # On macOS the default detection is "available"; force the env
    # to match so this test passes on Linux without DISPLAY.
    del monkeypatch  # placeholder for future signal-injection patches
    env: dict[str, str] = {}
    if platform.system() == "Linux":
        env["DISPLAY"] = ":0"
    avail = detect_browser_availability(env)
    assert avail.code in {"available"}
    assert avail.available is True
