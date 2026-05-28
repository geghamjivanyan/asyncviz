"""Cross-option validation for the canonical :class:`RuntimeOptions`.

Per-field type/range validators live in the per-domain modules (or
the originating dataclass constructors); this module owns the
cross-option rules that don't have an obvious home — e.g.
"``recording.enabled=True`` requires ``recording.output_path``".

Every failure raises :class:`RuntimeConfigurationError` with a list
of structured issues so callers can render every problem at once
rather than fixing-and-rerunning.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from asyncviz.configuration.runtime_options import RuntimeOptions


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One thing wrong with a resolved options struct."""

    field: str
    message: str

    def __str__(self) -> str:
        return f"{self.field}: {self.message}"


class RuntimeConfigurationError(ValueError):
    """Raised when one or more validation issues are detected."""

    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        super().__init__(self._render(issues))

    @staticmethod
    def _render(issues: tuple[ValidationIssue, ...]) -> str:
        if not issues:
            return "configuration invalid"
        if len(issues) == 1:
            return f"configuration invalid: {issues[0]}"
        body = "\n  - ".join(str(i) for i in issues)
        return f"configuration invalid:\n  - {body}"


def _check_network(options: RuntimeOptions) -> Iterable[ValidationIssue]:
    n = options.network
    if not (1 <= n.port <= 65_535):
        yield ValidationIssue("network.port", f"must be in 1..65535, got {n.port}")
    if not n.host:
        yield ValidationIssue("network.host", "must not be empty")
    if (
        options.security.bind_loopback_only
        and not options.security.allow_remote_connections
        and n.host not in {"127.0.0.1", "::1", "localhost"}
    ):
        yield ValidationIssue(
            "network.host",
            (
                f"host {n.host!r} is non-loopback but "
                "security.allow_remote_connections is False; "
                "set --security-allow-remote / ASYNCVIZ_ALLOW_REMOTE=1 to opt in"
            ),
        )


def _check_dashboard(options: RuntimeOptions) -> Iterable[ValidationIssue]:
    d = options.dashboard
    if d.heartbeat_interval_seconds <= 0:
        yield ValidationIssue(
            "dashboard.heartbeat_interval_seconds",
            f"must be > 0, got {d.heartbeat_interval_seconds}",
        )
    if d.startup_timeout_seconds < 0:
        yield ValidationIssue(
            "dashboard.startup_timeout_seconds",
            f"must be >= 0, got {d.startup_timeout_seconds}",
        )


def _check_monitoring(options: RuntimeOptions) -> Iterable[ValidationIssue]:
    m = options.monitoring
    if m.lag_sample_interval_ms <= 0:
        yield ValidationIssue(
            "monitoring.lag_sample_interval_ms",
            f"must be > 0, got {m.lag_sample_interval_ms}",
        )
    if not (0 < m.lag_warning_ms <= m.lag_critical_ms <= m.lag_freeze_ms):
        yield ValidationIssue(
            "monitoring.lag_*_ms",
            (
                "thresholds must satisfy 0 < warning ≤ critical ≤ freeze; "
                f"got warning={m.lag_warning_ms}, critical={m.lag_critical_ms}, "
                f"freeze={m.lag_freeze_ms}"
            ),
        )


def _check_recording(options: RuntimeOptions) -> Iterable[ValidationIssue]:
    r = options.recording
    if r.enabled and r.output_path is None:
        yield ValidationIssue(
            "recording.output_path",
            "recording.enabled is True but no output_path was supplied",
        )
    if r.chunk_events < 0:
        yield ValidationIssue("recording.chunk_events", "must be >= 0")
    if r.chunk_bytes < 0:
        yield ValidationIssue("recording.chunk_bytes", "must be >= 0")
    if r.queue_capacity <= 0:
        yield ValidationIssue("recording.queue_capacity", "must be > 0")
    if r.flush_interval_seconds < 0:
        yield ValidationIssue("recording.flush_interval_seconds", "must be >= 0")


def _check_replay(options: RuntimeOptions) -> Iterable[ValidationIssue]:
    p = options.replay
    if p.buffer_capacity <= 0:
        yield ValidationIssue("replay.buffer_capacity", "must be > 0")
    if p.retention_seconds < 0:
        yield ValidationIssue("replay.retention_seconds", "must be >= 0")


def _check_browser(options: RuntimeOptions) -> Iterable[ValidationIssue]:
    b = options.browser
    if b.policy not in {"auto", "always", "never"}:
        yield ValidationIssue(
            "browser.policy",
            f"must be auto/always/never, got {b.policy!r}",
        )


def collect_issues(options: RuntimeOptions) -> tuple[ValidationIssue, ...]:
    """Run every cross-option validator + return the aggregate issues."""
    issues: list[ValidationIssue] = []
    for check in (
        _check_network,
        _check_dashboard,
        _check_monitoring,
        _check_recording,
        _check_replay,
        _check_browser,
    ):
        issues.extend(check(options))
    return tuple(issues)


def validate_options(options: RuntimeOptions) -> None:
    """Raise :class:`RuntimeConfigurationError` if any validator fails."""
    issues = collect_issues(options)
    if issues:
        raise RuntimeConfigurationError(issues)
