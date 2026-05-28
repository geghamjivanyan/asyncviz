from __future__ import annotations

from asyncviz.cli.browser.browser_availability import BrowserAvailability
from asyncviz.cli.browser.browser_backpressure import BrowserBackpressureGuard
from asyncviz.cli.browser.browser_configuration import BrowserLaunchConfig
from asyncviz.cli.browser.browser_diagnostics import (
    get_last_launch,
    reset_last_launch,
)
from asyncviz.cli.browser.browser_launcher import BrowserLauncher
from asyncviz.cli.browser.browser_metrics import (
    get_browser_metrics,
    reset_browser_metrics,
)
from asyncviz.cli.browser.browser_policy import BrowserLaunchPolicy
from asyncviz.cli.browser.browser_preferences import BrowserPreferences
from asyncviz.cli.browser.browser_process import StubBackend
from asyncviz.cli.browser.browser_sessions import BrowserSessionGuard


def _avail(available: bool = True, code: str = "available") -> BrowserAvailability:
    return BrowserAvailability(available=available, code=code, reason="test")  # type: ignore[arg-type]


def _build_launcher(
    *,
    avail: BrowserAvailability | None = None,
    prefs: BrowserPreferences | None = None,
    backend: StubBackend | None = None,
    cap: int = 4,
) -> tuple[BrowserLauncher, StubBackend]:
    backend = backend or StubBackend(succeed=True)
    launcher = BrowserLauncher(
        backend=backend,
        session_guard=BrowserSessionGuard(),
        backpressure=BrowserBackpressureGuard(max_concurrent=cap),
        availability_fn=lambda: avail or _avail(),
        preferences_loader=lambda: prefs or BrowserPreferences(policy=None, hard_off=False),
        clock=lambda: 0.0,
        sleep=lambda _: None,
    )
    return launcher, backend


def setup_function(_fn: object) -> None:
    reset_browser_metrics()
    reset_last_launch()


def test_launcher_opens_when_available_and_auto() -> None:
    launcher, backend = _build_launcher()
    cfg = BrowserLaunchConfig(
        url="http://test/",
        policy=BrowserLaunchPolicy.AUTO,
        readiness_url=None,
        launch_delay_seconds=0,
    )
    stats = launcher.launch(cfg)
    assert stats.status == "opened"
    assert backend.calls == ["http://test/"]
    assert get_browser_metrics().snapshot().launches_opened == 1


def test_launcher_skips_when_policy_never() -> None:
    launcher, backend = _build_launcher()
    cfg = BrowserLaunchConfig(
        url="http://test/",
        policy=BrowserLaunchPolicy.NEVER,
        readiness_url=None,
        launch_delay_seconds=0,
    )
    stats = launcher.launch(cfg)
    assert stats.status == "skipped"
    assert backend.calls == []
    assert get_browser_metrics().snapshot().launches_skipped == 1


def test_launcher_skips_when_headless_auto() -> None:
    launcher, backend = _build_launcher(avail=_avail(available=False, code="ci"))
    cfg = BrowserLaunchConfig(
        url="http://test/",
        policy=BrowserLaunchPolicy.AUTO,
        readiness_url=None,
        launch_delay_seconds=0,
    )
    stats = launcher.launch(cfg)
    assert stats.status == "skipped"
    assert backend.calls == []


def test_launcher_always_overrides_unavailable() -> None:
    launcher, backend = _build_launcher(avail=_avail(available=False, code="ci"))
    cfg = BrowserLaunchConfig(
        url="http://test/",
        policy=BrowserLaunchPolicy.ALWAYS,
        readiness_url=None,
        launch_delay_seconds=0,
    )
    stats = launcher.launch(cfg)
    assert stats.status == "opened"
    assert backend.calls == ["http://test/"]


def test_launcher_dedup_via_session_id() -> None:
    launcher, backend = _build_launcher()
    cfg = BrowserLaunchConfig(
        url="http://test/",
        policy=BrowserLaunchPolicy.ALWAYS,
        readiness_url=None,
        session_id="rt-1",
        launch_delay_seconds=0,
    )
    first = launcher.launch(cfg)
    second = launcher.launch(cfg)
    assert first.status == "opened"
    assert second.status == "deduped"
    assert backend.calls == ["http://test/"]


def test_launcher_records_throttled_when_cap_reached() -> None:
    launcher, _backend = _build_launcher(cap=1)
    cfg = BrowserLaunchConfig(
        url="http://test/",
        policy=BrowserLaunchPolicy.ALWAYS,
        readiness_url=None,
        launch_delay_seconds=0,
    )
    # Acquire the only slot then re-enter without releasing.
    launcher.backpressure.acquire()
    stats = launcher.launch(cfg)
    assert stats.status == "throttled"
    assert "backpressure" in stats.detail
    launcher.backpressure.release()


def test_launcher_failed_status_when_backend_returns_false() -> None:
    backend = StubBackend(succeed=False)
    launcher, _ = _build_launcher(backend=backend)
    cfg = BrowserLaunchConfig(
        url="http://test/",
        policy=BrowserLaunchPolicy.ALWAYS,
        readiness_url=None,
        launch_delay_seconds=0,
    )
    stats = launcher.launch(cfg)
    assert stats.status == "failed"
    assert get_browser_metrics().snapshot().launches_failed == 1


def test_launcher_hard_off_prevents_open_even_with_always() -> None:
    launcher, backend = _build_launcher(
        prefs=BrowserPreferences(policy=None, hard_off=True),
    )
    cfg = BrowserLaunchConfig(
        url="http://test/",
        policy=BrowserLaunchPolicy.ALWAYS,
        readiness_url=None,
        launch_delay_seconds=0,
    )
    stats = launcher.launch(cfg)
    assert stats.status == "skipped"
    assert "ASYNCVIZ_NO_BROWSER" in stats.detail
    assert backend.calls == []


def test_launcher_records_last_launch_for_diagnostics() -> None:
    launcher, _ = _build_launcher()
    cfg = BrowserLaunchConfig(
        url="http://test/",
        policy=BrowserLaunchPolicy.ALWAYS,
        readiness_url=None,
        launch_delay_seconds=0,
    )
    launcher.launch(cfg)
    assert get_last_launch() is not None
    assert get_last_launch().opened  # type: ignore[union-attr]


def test_launcher_uses_readiness_probe(monkeypatch) -> None:
    """When ``readiness_url`` is set the launcher waits + records metrics."""
    launcher, backend = _build_launcher()
    cfg = BrowserLaunchConfig(
        url="http://test/",
        policy=BrowserLaunchPolicy.ALWAYS,
        readiness_url="http://test/health",
        readiness_timeout_seconds=1.0,
        readiness_interval_seconds=0.01,
        launch_delay_seconds=0,
    )
    # Patch the probe function used inside the probe.
    import asyncviz.cli.browser.browser_readiness as readiness_mod

    monkeypatch.setattr(readiness_mod, "_http_probe_once", lambda _u, _t: True)
    stats = launcher.launch(cfg)
    assert stats.readiness is not None
    assert stats.readiness.kind == "ready"
    assert stats.status == "opened"
    assert backend.calls == ["http://test/"]
