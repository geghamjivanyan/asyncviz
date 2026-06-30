"""Canonical orchestrator for opening the dashboard in a browser.

Composition order:

  1. **Availability** — :func:`detect_browser_availability` probes
     the environment for headless / CI / SSH signals.
  2. **Preferences** — env-derived overrides layered on top.
  3. **Policy** — :func:`decide` resolves AUTO / ALWAYS / NEVER into
     a verdict.
  4. **Session guard** — open-once dedup.
  5. **Backpressure** — bounded concurrency cap.
  6. **Readiness** — block until the dashboard responds.
  7. **Process** — issue the actual ``webbrowser.open`` call.
  8. **Statistics + diagnostics** — record the outcome.

The launcher is async-shape: :meth:`launch_async` schedules the work
on a daemon thread + returns a provisional outcome immediately.
Callers that need the final state (tests, the diagnostics endpoint)
use :meth:`launch`.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from asyncviz.cli.browser.browser_availability import BrowserAvailability
from asyncviz.cli.browser.browser_backpressure import (
    BrowserBackpressureGuard,
    get_default_backpressure_guard,
)
from asyncviz.cli.browser.browser_configuration import BrowserLaunchConfig
from asyncviz.cli.browser.browser_detection import detect_browser_availability
from asyncviz.cli.browser.browser_diagnostics import record_last_launch
from asyncviz.cli.browser.browser_metrics import get_browser_metrics
from asyncviz.cli.browser.browser_policy import PolicyDecision, decide
from asyncviz.cli.browser.browser_preferences import (
    BrowserPreferences,
    load_preferences,
)
from asyncviz.cli.browser.browser_process import (
    BrowserBackend,
    ProcessLaunchOutcome,
    default_backend,
)
from asyncviz.cli.browser.browser_readiness import (
    ProbeOutcome,
    ReadinessProbe,
)
from asyncviz.cli.browser.browser_sessions import (
    BrowserSessionGuard,
    get_default_session_guard,
)
from asyncviz.cli.browser.browser_statistics import LaunchStatistics
from asyncviz.cli.browser.browser_tracing import record_browser_trace

# ── Backwards-compatible outcome shape ────────────────────────────────


@dataclass(frozen=True, slots=True)
class BrowserLaunchOutcome:
    """Result returned by :func:`launch_browser` (legacy API).

    Mirrors the v1 shape so existing tests + callers keep working.
    New code prefers :class:`LaunchStatistics` (richer).
    """

    requested: bool
    launched: bool
    status: Literal["opened", "skipped", "failed", "throttled", "deduped"]
    detail: str


def launch_browser(
    url: str,
    *,
    requested: bool,
    delay: float = 0.2,
) -> BrowserLaunchOutcome:
    """Legacy launcher entry-point.

    Routes through :class:`BrowserLauncher` so the new diagnostics +
    metrics fire even for callers that haven't migrated to the typed
    config API. ``requested`` is interpreted as
    ``always`` (open) or ``never`` (skip) so existing callers don't
    need a policy.
    """
    config = BrowserLaunchConfig(
        url=url,
        policy="always" if requested else "never",  # type: ignore[arg-type]
        launch_delay_seconds=delay,
        readiness_url=None,
    )
    stats = BrowserLauncher().launch(config)
    return BrowserLaunchOutcome(
        requested=requested,
        launched=stats.opened,
        status=stats.status,
        detail=stats.detail,
    )


# ── Canonical launcher ────────────────────────────────────────────────


AvailabilityFn = Callable[[], BrowserAvailability]
PreferencesFn = Callable[[], BrowserPreferences]


@dataclass(slots=True)
class BrowserLauncher:
    """Composed browser-launch orchestrator.

    Dependencies are injectable so tests can swap the readiness
    probe, the platform backend, the session guard, etc., without
    monkey-patching globals.
    """

    backend: BrowserBackend = field(default_factory=default_backend)
    session_guard: BrowserSessionGuard = field(default_factory=get_default_session_guard)
    backpressure: BrowserBackpressureGuard = field(default_factory=get_default_backpressure_guard)
    availability_fn: AvailabilityFn = field(default=detect_browser_availability)
    preferences_loader: PreferencesFn = field(default=load_preferences)
    clock: Callable[[], float] = field(default=time.monotonic)
    sleep: Callable[[float], None] = field(default=time.sleep)

    # ── Public API ────────────────────────────────────────────────

    def launch(self, config: BrowserLaunchConfig) -> LaunchStatistics:
        """Synchronously decide + (optionally) wait + launch.

        Returns the composed :class:`LaunchStatistics`. Records into
        the diagnostics singletons as a side effect.
        """
        return self._do_launch(config)

    def launch_async(self, config: BrowserLaunchConfig) -> BrowserLaunchOutcome:
        """Schedule the launch on a daemon thread + return immediately.

        The provisional outcome reflects the policy decision; the
        real platform outcome lands in the diagnostics singletons
        when the thread finishes.
        """
        availability = self._resolve_availability(config)
        prefs = self.preferences_loader()
        if prefs.hard_off:
            stats = self._build_skipped_stats(
                config,
                availability=availability,
                detail="ASYNCVIZ_NO_BROWSER set",
            )
            self._finalize(stats)
            return _outcome_from(stats, requested=False)

        decision = decide(prefs.policy or config.policy, availability)
        record_browser_trace("policy-resolved", decision.reason)

        if decision.skipped:
            stats = self._build_skipped_stats(
                config,
                availability=availability,
                detail=decision.reason,
            )
            self._finalize(stats)
            return _outcome_from(stats, requested=False)

        if not self.session_guard.should_open(config.session_id):
            stats = self._build_deduped_stats(config, availability=availability)
            self._finalize(stats)
            return _outcome_from(stats, requested=True)

        if not self.backpressure.acquire():
            stats = self._build_throttled_stats(config, availability=availability)
            self._finalize(stats)
            return _outcome_from(stats, requested=True)

        provisional = BrowserLaunchOutcome(
            requested=True,
            launched=True,
            status="opened",
            detail="launch scheduled",
        )

        def _worker() -> None:
            try:
                stats = self._wait_then_open(
                    config,
                    availability=availability,
                    decision=decision,
                )
                self._finalize(stats)
            finally:
                self.backpressure.release()

        thread = threading.Thread(
            target=_worker,
            name="asyncviz-cli-browser",
            daemon=True,
        )
        thread.start()
        return provisional

    # ── Internals ─────────────────────────────────────────────────

    def _resolve_availability(self, config: BrowserLaunchConfig) -> BrowserAvailability:
        # ``availability_fn`` ignores ``config`` today; the parameter
        # is here so a future detector can use the URL to pick a
        # per-host policy.
        del config
        return self.availability_fn()

    def _do_launch(self, config: BrowserLaunchConfig) -> LaunchStatistics:
        availability = self._resolve_availability(config)
        prefs = self.preferences_loader()
        if prefs.hard_off:
            stats = self._build_skipped_stats(
                config,
                availability=availability,
                detail="ASYNCVIZ_NO_BROWSER set",
            )
            self._finalize(stats)
            return stats

        decision = decide(prefs.policy or config.policy, availability)
        record_browser_trace("policy-resolved", decision.reason)
        if decision.skipped:
            stats = self._build_skipped_stats(
                config,
                availability=availability,
                detail=decision.reason,
            )
            self._finalize(stats)
            return stats

        if not self.session_guard.should_open(config.session_id):
            stats = self._build_deduped_stats(config, availability=availability)
            self._finalize(stats)
            return stats

        if not self.backpressure.acquire():
            stats = self._build_throttled_stats(config, availability=availability)
            self._finalize(stats)
            return stats

        try:
            stats = self._wait_then_open(
                config,
                availability=availability,
                decision=decision,
            )
        finally:
            self.backpressure.release()
        self._finalize(stats)
        return stats

    def _wait_then_open(
        self,
        config: BrowserLaunchConfig,
        *,
        availability: BrowserAvailability,
        decision: PolicyDecision,
    ) -> LaunchStatistics:
        started = self.clock()
        record_browser_trace("launch-attempt", config.url)
        get_browser_metrics().record_attempt()

        readiness: ProbeOutcome | None = None
        if config.readiness_url is not None:
            readiness = self._await_readiness(config)
        elif config.launch_delay_seconds > 0:
            self.sleep(config.launch_delay_seconds)

        try:
            process = self.backend.open(config.url)
        except Exception as exc:  # pragma: no cover — defensive
            process = ProcessLaunchOutcome(
                success=False,
                detail=f"backend raised: {exc}",
            )

        elapsed = max(0.0, self.clock() - started)
        if process.success:
            get_browser_metrics().record_opened()
            record_browser_trace("launch-opened", config.url)
            return LaunchStatistics(
                status="opened",
                url=config.url,
                policy=decision,
                availability=availability,
                readiness=readiness,
                process=process,
                elapsed_seconds=elapsed,
                detail=process.detail,
            )
        get_browser_metrics().record_failed()
        record_browser_trace("launch-failed", process.detail)
        return LaunchStatistics(
            status="failed",
            url=config.url,
            policy=decision,
            availability=availability,
            readiness=readiness,
            process=process,
            elapsed_seconds=elapsed,
            detail=process.detail,
        )

    def _await_readiness(self, config: BrowserLaunchConfig) -> ProbeOutcome:
        # Resolve ``_http_probe_once`` at call time so tests that
        # monkey-patch the module attribute still affect the probe.
        from asyncviz.cli.browser import browser_readiness as _readiness_mod

        probe = ReadinessProbe(
            url=config.readiness_url,
            timeout_seconds=config.readiness_timeout_seconds,
            interval_seconds=config.readiness_interval_seconds,
            probe_once=_readiness_mod._http_probe_once,
            clock=self.clock,
            sleep=self.sleep,
        )
        record_browser_trace("readiness-start", config.readiness_url or "")
        outcome = probe.wait()
        if outcome.kind == "ready":
            record_browser_trace(
                "readiness-success",
                f"attempts={outcome.attempts} elapsed={outcome.elapsed_seconds:.2f}s",
            )
        elif outcome.kind == "timeout":
            record_browser_trace(
                "readiness-timeout",
                f"attempts={outcome.attempts} elapsed={outcome.elapsed_seconds:.2f}s",
            )
        get_browser_metrics().record_readiness(
            elapsed_seconds=outcome.elapsed_seconds,
            timed_out=outcome.kind == "timeout",
        )
        return outcome

    def _build_skipped_stats(
        self,
        config: BrowserLaunchConfig,
        *,
        availability: BrowserAvailability,
        detail: str,
    ) -> LaunchStatistics:
        decision = decide(config.policy, availability)
        get_browser_metrics().record_skipped()
        record_browser_trace("launch-skipped", detail)
        return LaunchStatistics(
            status="skipped",
            url=config.url,
            policy=decision,
            availability=availability,
            readiness=None,
            process=None,
            elapsed_seconds=0.0,
            detail=detail,
        )

    def _build_throttled_stats(
        self,
        config: BrowserLaunchConfig,
        *,
        availability: BrowserAvailability,
    ) -> LaunchStatistics:
        decision = decide(config.policy, availability)
        get_browser_metrics().record_throttled()
        record_browser_trace("launch-throttled", config.url)
        return LaunchStatistics(
            status="throttled",
            url=config.url,
            policy=decision,
            availability=availability,
            readiness=None,
            process=None,
            elapsed_seconds=0.0,
            detail=(
                "skipped: backpressure cap reached "
                f"({self.backpressure.max_concurrent} concurrent launches)"
            ),
        )

    def _build_deduped_stats(
        self,
        config: BrowserLaunchConfig,
        *,
        availability: BrowserAvailability,
    ) -> LaunchStatistics:
        decision = decide(config.policy, availability)
        get_browser_metrics().record_deduped()
        record_browser_trace("launch-deduped", config.session_id or "<no-session>")
        return LaunchStatistics(
            status="deduped",
            url=config.url,
            policy=decision,
            availability=availability,
            readiness=None,
            process=None,
            elapsed_seconds=0.0,
            detail=f"skipped: session {config.session_id!r} already opened",
        )

    def _finalize(self, stats: LaunchStatistics) -> None:
        get_browser_metrics().record_peak_in_flight(self.backpressure.peak)
        record_last_launch(stats)


def _outcome_from(stats: LaunchStatistics, *, requested: bool) -> BrowserLaunchOutcome:
    return BrowserLaunchOutcome(
        requested=requested,
        launched=stats.opened,
        status=stats.status,
        detail=stats.detail,
    )
