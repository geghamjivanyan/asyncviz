from __future__ import annotations

from asyncviz.cli.browser.browser_availability import BrowserAvailability
from asyncviz.cli.browser.browser_backpressure import BrowserBackpressureGuard
from asyncviz.cli.browser.browser_configuration import BrowserLaunchConfig
from asyncviz.cli.browser.browser_diagnostics import (
    build_browser_diagnostics,
    reset_last_launch,
)
from asyncviz.cli.browser.browser_launcher import BrowserLauncher
from asyncviz.cli.browser.browser_metrics import reset_browser_metrics
from asyncviz.cli.browser.browser_policy import BrowserLaunchPolicy
from asyncviz.cli.browser.browser_preferences import BrowserPreferences
from asyncviz.cli.browser.browser_process import StubBackend
from asyncviz.cli.browser.browser_sessions import BrowserSessionGuard
from asyncviz.cli.browser.browser_tracing import (
    clear_browser_trace,
    set_browser_trace_enabled,
)


def setup_function(_fn: object) -> None:
    reset_browser_metrics()
    reset_last_launch()
    clear_browser_trace()
    set_browser_trace_enabled(False)


def _avail() -> BrowserAvailability:
    return BrowserAvailability(available=True, code="available", reason="test")


def _launcher(backend: StubBackend) -> BrowserLauncher:
    return BrowserLauncher(
        backend=backend,
        session_guard=BrowserSessionGuard(),
        backpressure=BrowserBackpressureGuard(max_concurrent=4),
        availability_fn=_avail,
        preferences_loader=lambda: BrowserPreferences(policy=None, hard_off=False),
        clock=lambda: 0.0,
        sleep=lambda _: None,
    )


def test_diagnostics_records_last_launch() -> None:
    backend = StubBackend(succeed=True)
    launcher = _launcher(backend)
    launcher.launch(
        BrowserLaunchConfig(
            url="http://x/",
            policy=BrowserLaunchPolicy.ALWAYS,
            readiness_url=None,
            launch_delay_seconds=0,
        ),
    )
    diag = build_browser_diagnostics()
    assert diag.last_launch is not None
    assert diag.last_launch.opened is True
    assert diag.metrics.launches_opened == 1


def test_diagnostics_to_dict_is_json_friendly() -> None:
    backend = StubBackend(succeed=True)
    _launcher(backend).launch(
        BrowserLaunchConfig(
            url="http://x/",
            policy=BrowserLaunchPolicy.ALWAYS,
            readiness_url=None,
            launch_delay_seconds=0,
        ),
    )
    payload = build_browser_diagnostics().to_dict()
    assert payload["metrics"]["launches_opened"] == 1
    assert payload["last_launch"]["url"] == "http://x/"


def test_trace_ring_records_events_when_enabled() -> None:
    set_browser_trace_enabled(True)
    backend = StubBackend(succeed=True)
    _launcher(backend).launch(
        BrowserLaunchConfig(
            url="http://x/",
            policy=BrowserLaunchPolicy.ALWAYS,
            readiness_url=None,
            launch_delay_seconds=0,
        ),
    )
    diag = build_browser_diagnostics()
    assert diag.trace_enabled is True
    kinds = {entry.kind for entry in diag.recent_trace}
    assert "launch-attempt" in kinds
    assert "launch-opened" in kinds


def test_trace_ring_silent_when_disabled() -> None:
    backend = StubBackend(succeed=True)
    _launcher(backend).launch(
        BrowserLaunchConfig(
            url="http://x/",
            policy=BrowserLaunchPolicy.ALWAYS,
            readiness_url=None,
            launch_delay_seconds=0,
        ),
    )
    diag = build_browser_diagnostics()
    assert diag.trace_enabled is False
    assert diag.recent_trace == ()
