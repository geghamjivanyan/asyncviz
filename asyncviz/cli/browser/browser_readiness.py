"""Dashboard readiness probe.

Polls a URL until it responds 2xx (or the timeout elapses). Used by
the launcher so we only open a browser tab once the server is
actually serving — operators see a working page instead of a "this
site can't be reached" error.

The probe uses :mod:`urllib` so we don't pull ``httpx`` / ``aiohttp``
into the cold-start path; the request is tiny and the loop sleeps
between attempts so it never burns CPU.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

ProbeOutcomeKind = Literal["ready", "timeout", "disabled", "error"]


@dataclass(frozen=True, slots=True)
class ProbeOutcome:
    """Structured probe result.

    Carries the attempt count + total elapsed seconds so callers can
    report "waited 1.2s across 12 polls" without re-instrumenting.
    """

    kind: ProbeOutcomeKind
    attempts: int
    elapsed_seconds: float
    detail: str = ""


#: A single probe call; returns True on a 2xx, False otherwise.
ProbeOnce = Callable[[str, float], bool]


def _http_probe_once(url: str, timeout: float) -> bool:
    """Issue one HTTP HEAD-equivalent GET; True on 2xx, False on anything else."""
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, OSError, ConnectionError):
        return False


@dataclass(slots=True)
class ReadinessProbe:
    """Polling readiness checker.

    Default probe is HTTP; tests inject a custom ``probe_once``
    callable so they can exercise success / failure / slow-ready
    semantics without an HTTP server.
    """

    url: str | None
    timeout_seconds: float
    interval_seconds: float
    probe_once: ProbeOnce = _http_probe_once
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep

    def wait(self) -> ProbeOutcome:
        """Block until the URL responds 2xx or the timeout elapses."""
        if self.url is None:
            return ProbeOutcome(
                kind="disabled",
                attempts=0,
                elapsed_seconds=0.0,
                detail="no readiness URL configured",
            )
        if self.timeout_seconds <= 0:
            return ProbeOutcome(
                kind="disabled",
                attempts=0,
                elapsed_seconds=0.0,
                detail="non-positive timeout",
            )
        started = self.clock()
        deadline = started + self.timeout_seconds
        attempts = 0
        last_error = ""
        while True:
            attempts += 1
            try:
                ok = self.probe_once(self.url, min(self.interval_seconds, 1.0))
            except Exception as exc:  # pragma: no cover — defensive
                ok = False
                last_error = str(exc)
            if ok:
                return ProbeOutcome(
                    kind="ready",
                    attempts=attempts,
                    elapsed_seconds=max(0.0, self.clock() - started),
                    detail="probe succeeded",
                )
            now = self.clock()
            if now >= deadline:
                return ProbeOutcome(
                    kind="timeout",
                    attempts=attempts,
                    elapsed_seconds=max(0.0, now - started),
                    detail=last_error or "probe did not succeed before timeout",
                )
            self.sleep(min(self.interval_seconds, max(0.0, deadline - now)))
