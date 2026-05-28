from __future__ import annotations

from asyncviz.cli.browser.browser_policy import BrowserLaunchPolicy
from asyncviz.cli.browser.browser_preferences import (
    ENV_BROWSER_POLICY,
    ENV_NO_BROWSER,
    load_preferences,
)


def test_load_preferences_empty_env() -> None:
    prefs = load_preferences({})
    assert prefs.policy is None
    assert prefs.hard_off is False


def test_load_preferences_honors_hard_off() -> None:
    prefs = load_preferences({ENV_NO_BROWSER: "1"})
    assert prefs.hard_off is True


def test_load_preferences_picks_policy_from_env() -> None:
    prefs = load_preferences({ENV_BROWSER_POLICY: "always"})
    assert prefs.policy is BrowserLaunchPolicy.ALWAYS


def test_load_preferences_ignores_unknown_policy() -> None:
    prefs = load_preferences({ENV_BROWSER_POLICY: "yolo"})
    assert prefs.policy is None


def test_load_preferences_hard_off_truthy_variants() -> None:
    for value in ("1", "true", "YES", "on"):
        prefs = load_preferences({ENV_NO_BROWSER: value})
        assert prefs.hard_off is True, value


def test_load_preferences_hard_off_falsy_variants() -> None:
    for value in ("0", "false", "no", ""):
        prefs = load_preferences({ENV_NO_BROWSER: value})
        assert prefs.hard_off is False, value
