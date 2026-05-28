"""Degradation-policy tests."""

from __future__ import annotations

from asyncviz.runtime.resilience import BreakerState, derive_runtime_mode


def test_empty_states_means_normal() -> None:
    assert derive_runtime_mode(states={}) == "normal"


def test_all_closed_means_normal() -> None:
    assert (
        derive_runtime_mode(
            states={"replay": BreakerState.CLOSED, "websocket": BreakerState.CLOSED},
        )
        == "normal"
    )


def test_one_non_critical_open_means_degraded() -> None:
    assert (
        derive_runtime_mode(
            states={"render": BreakerState.OPEN, "websocket": BreakerState.CLOSED},
        )
        == "degraded"
    )


def test_two_subsystems_open_means_shed() -> None:
    assert (
        derive_runtime_mode(
            states={
                "render": BreakerState.OPEN,
                "websocket": BreakerState.OPEN,
                "reducer": BreakerState.CLOSED,
            },
        )
        == "shed"
    )


def test_critical_open_means_emergency() -> None:
    assert (
        derive_runtime_mode(
            states={
                "replay": BreakerState.OPEN,
                "websocket": BreakerState.CLOSED,
            },
        )
        == "emergency"
    )


def test_halt_on_critical_flag() -> None:
    assert (
        derive_runtime_mode(
            states={"replay": BreakerState.OPEN},
            halt_on_critical=True,
        )
        == "halt"
    )


def test_half_open_counts_as_degraded() -> None:
    assert (
        derive_runtime_mode(
            states={"render": BreakerState.HALF_OPEN, "websocket": BreakerState.CLOSED},
        )
        == "degraded"
    )
