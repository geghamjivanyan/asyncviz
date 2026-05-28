from __future__ import annotations

from asyncviz.cli.browser.browser_readiness import ProbeOutcome, ReadinessProbe


def _clock_factory(values: list[float]):
    iterator = iter(values)

    def _clock() -> float:
        try:
            return next(iterator)
        except StopIteration:
            return values[-1]

    return _clock


def test_probe_returns_disabled_when_url_is_none() -> None:
    probe = ReadinessProbe(url=None, timeout_seconds=1.0, interval_seconds=0.01)
    outcome = probe.wait()
    assert outcome.kind == "disabled"
    assert outcome.attempts == 0


def test_probe_returns_disabled_for_non_positive_timeout() -> None:
    probe = ReadinessProbe(
        url="http://example.test/health",
        timeout_seconds=0,
        interval_seconds=0.01,
    )
    assert probe.wait().kind == "disabled"


def test_probe_returns_ready_when_first_probe_succeeds() -> None:
    calls: list[str] = []

    def probe_once(url: str, _timeout: float) -> bool:
        calls.append(url)
        return True

    probe = ReadinessProbe(
        url="http://example.test/health",
        timeout_seconds=1.0,
        interval_seconds=0.01,
        probe_once=probe_once,
        clock=_clock_factory([0.0, 0.01]),
        sleep=lambda _: None,
    )
    outcome = probe.wait()
    assert outcome.kind == "ready"
    assert outcome.attempts == 1
    assert calls == ["http://example.test/health"]


def test_probe_succeeds_after_several_attempts() -> None:
    attempts = {"n": 0}

    def probe_once(_url: str, _timeout: float) -> bool:
        attempts["n"] += 1
        return attempts["n"] == 3

    probe = ReadinessProbe(
        url="http://x/health",
        timeout_seconds=10.0,
        interval_seconds=0.01,
        probe_once=probe_once,
        clock=_clock_factory([0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]),
        sleep=lambda _: None,
    )
    outcome = probe.wait()
    assert outcome.kind == "ready"
    assert outcome.attempts == 3


def test_probe_times_out_when_never_ready() -> None:
    def probe_once(_url: str, _timeout: float) -> bool:
        return False

    # Clock advances past the deadline after a few sleeps.
    probe = ReadinessProbe(
        url="http://x/health",
        timeout_seconds=0.05,
        interval_seconds=0.01,
        probe_once=probe_once,
        clock=_clock_factory([0.0, 0.0, 0.02, 0.04, 0.06]),
        sleep=lambda _: None,
    )
    outcome = probe.wait()
    assert outcome.kind == "timeout"
    assert outcome.attempts >= 1


def test_probe_outcome_dataclass_carries_metadata() -> None:
    outcome = ProbeOutcome(kind="ready", attempts=3, elapsed_seconds=0.5)
    assert outcome.attempts == 3
    assert outcome.elapsed_seconds == 0.5
