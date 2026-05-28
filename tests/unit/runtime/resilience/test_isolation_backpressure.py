"""Isolation-backpressure bridge tests."""

from __future__ import annotations

from asyncviz.runtime.resilience import IsolationBackpressureBridge


def test_starts_in_normal_suggestion() -> None:
    bridge = IsolationBackpressureBridge()
    suggestion = bridge.current_suggestion()
    assert suggestion.runtime_mode == "normal"
    assert suggestion.suggested_drop_policy == "drop-low-priority"


def test_on_mode_change_updates_suggestion() -> None:
    bridge = IsolationBackpressureBridge()
    suggestion = bridge.on_mode_change("emergency")
    assert suggestion.runtime_mode == "emergency"
    assert suggestion.suggested_drop_policy == "drop-newest"
    assert bridge.current_mode() == "emergency"


def test_subscribe_receives_updates() -> None:
    bridge = IsolationBackpressureBridge()
    received = []
    bridge.subscribe(lambda s: received.append(s.runtime_mode))
    bridge.on_mode_change("degraded")
    bridge.on_mode_change("emergency")
    assert received == ["degraded", "emergency"]


def test_duplicate_mode_does_not_notify() -> None:
    bridge = IsolationBackpressureBridge()
    received = []
    bridge.subscribe(lambda s: received.append(s.runtime_mode))
    bridge.on_mode_change("degraded")
    bridge.on_mode_change("degraded")
    assert received == ["degraded"]


def test_unsubscribe() -> None:
    bridge = IsolationBackpressureBridge()
    received = []
    unsub = bridge.subscribe(lambda s: received.append(s.runtime_mode))
    bridge.on_mode_change("degraded")
    unsub()
    bridge.on_mode_change("emergency")
    assert received == ["degraded"]


def test_listener_exception_is_isolated() -> None:
    bridge = IsolationBackpressureBridge()

    def _bad(_s: object) -> None:
        raise RuntimeError("listener failure")

    bridge.subscribe(_bad)
    # Must not raise.
    bridge.on_mode_change("halt")
    assert bridge.current_mode() == "halt"
