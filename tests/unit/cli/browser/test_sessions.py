from __future__ import annotations

from asyncviz.cli.browser.browser_sessions import (
    BrowserSessionGuard,
    get_default_session_guard,
    reset_default_session_guard,
)


def setup_function(_fn: object) -> None:
    reset_default_session_guard()


def test_should_open_returns_true_for_none_session() -> None:
    guard = BrowserSessionGuard()
    assert guard.should_open(None) is True
    assert guard.should_open(None) is True


def test_should_open_dedup_per_session_id() -> None:
    guard = BrowserSessionGuard()
    assert guard.should_open("rt-1") is True
    assert guard.should_open("rt-1") is False
    assert guard.should_open("rt-2") is True


def test_reset_clears_state() -> None:
    guard = BrowserSessionGuard()
    guard.should_open("rt-1")
    guard.reset("rt-1")
    assert guard.should_open("rt-1") is True


def test_reset_without_id_clears_all() -> None:
    guard = BrowserSessionGuard()
    guard.should_open("a")
    guard.should_open("b")
    guard.reset()
    assert guard.should_open("a") is True
    assert guard.should_open("b") is True


def test_default_guard_is_singleton() -> None:
    assert get_default_session_guard() is get_default_session_guard()
