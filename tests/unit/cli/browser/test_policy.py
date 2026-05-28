from __future__ import annotations

import pytest

from asyncviz.cli.browser.browser_availability import BrowserAvailability
from asyncviz.cli.browser.browser_policy import (
    BrowserLaunchPolicy,
    decide,
    resolve_policy,
)


def _avail(available: bool, code: str = "available") -> BrowserAvailability:
    return BrowserAvailability(available=available, code=code, reason="t")  # type: ignore[arg-type]


def test_resolve_policy_accepts_strings_and_enums() -> None:
    assert resolve_policy("auto") is BrowserLaunchPolicy.AUTO
    assert resolve_policy("ALWAYS") is BrowserLaunchPolicy.ALWAYS
    assert resolve_policy(BrowserLaunchPolicy.NEVER) is BrowserLaunchPolicy.NEVER


def test_resolve_policy_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        resolve_policy("yolo")


def test_resolve_policy_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        resolve_policy(123)  # type: ignore[arg-type]


def test_decide_always_overrides_unavailable() -> None:
    d = decide("always", _avail(available=False, code="ci"))
    assert d.open is True
    assert "forced" in d.reason
    assert d.policy is BrowserLaunchPolicy.ALWAYS


def test_decide_never_overrides_available() -> None:
    d = decide("never", _avail(available=True))
    assert d.open is False
    assert "never" in d.reason


def test_decide_auto_opens_when_available() -> None:
    d = decide("auto", _avail(available=True))
    assert d.open is True


def test_decide_auto_skips_when_unavailable() -> None:
    d = decide("auto", _avail(available=False, code="ssh-no-display"))
    assert d.open is False
    assert d.skipped is True
