from __future__ import annotations

import platform
import webbrowser

import pytest

from asyncviz.cli.browser import browser_detection
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
    # On Linux without DISPLAY the detector short-circuits to
    # ``no-display``; force the env so the detector falls through to
    # the ``webbrowser.get()`` probe.
    env: dict[str, str] = {}
    if platform.system() == "Linux":
        env["DISPLAY"] = ":0"

    # Headless CI runners (GitHub Actions Linux) do not register any
    # system browser, so a real ``webbrowser.get()`` call raises and
    # the detector returns ``no-browser-registered`` — which has
    # nothing to do with the env-detection logic this test exercises.
    # Stub the lookup so the test is environment-independent.
    def _fake_get() -> object:
        return object()

    monkeypatch.setattr(browser_detection.webbrowser, "get", _fake_get)

    avail = detect_browser_availability(env)
    assert avail.code in {"available"}
    assert avail.available is True


def test_detect_browser_marks_no_browser_registered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pin the ``no-browser-registered`` path so we know it still fires
    when ``webbrowser.get()`` actually raises — this is the path that
    headless CI runners exercise in practice."""
    env: dict[str, str] = {}
    if platform.system() == "Linux":
        env["DISPLAY"] = ":0"

    def _raises() -> object:
        raise webbrowser.Error("no browser registered")

    monkeypatch.setattr(browser_detection.webbrowser, "get", _raises)

    avail = detect_browser_availability(env)
    assert not avail.available
    assert avail.code == "no-browser-registered"
