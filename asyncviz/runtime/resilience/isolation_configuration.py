"""Runtime-failure-isolation configuration.

Three presets cover the realistic range:

* :func:`default_config` — production-balanced. Trips a breaker
  after a handful of failures inside a short window, holds the
  circuit open briefly, then re-probes.
* :func:`lean_config` — fast trip + fast recovery. Used in
  embedded / latency-critical deployments where lingering on a
  bad subsystem costs more than a few duplicate retries.
* :func:`relaxed_config` — high failure budget + long hold. For
  noisy environments where transient failures are common and we
  want to avoid premature degradation.

Each subsystem registered with the manager has its own
:class:`SubsystemPolicy`. Operators that want to override a single
domain (e.g. "give the recorder a bigger budget than the renderer")
construct a custom :class:`IsolationConfig`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

EmergencyMode = Literal[
    "normal",
    "degraded",
    "shed",
    "emergency",
    "halt",
]
"""Coarse runtime modes the manager can enter.

* ``normal`` — every subsystem healthy.
* ``degraded`` — one or more subsystems running on a documented
  fallback path.
* ``shed`` — overload shedding active; non-critical traffic dropped.
* ``emergency`` — replay/websocket isolated; critical paths only.
* ``halt`` — runtime is refusing new work to preserve current
  state for diagnostics.
"""

DEFAULT_FAILURE_WINDOW_S: Final[float] = 30.0
DEFAULT_FAILURE_THRESHOLD: Final[int] = 5
DEFAULT_OPEN_DURATION_S: Final[float] = 5.0
DEFAULT_HALF_OPEN_PROBES: Final[int] = 1
DEFAULT_RECOVERY_BACKOFF_S: Final[float] = 1.0
DEFAULT_MAX_RECOVERY_ATTEMPTS: Final[int] = 6
DEFAULT_TRACE_CAPACITY: Final[int] = 256


@dataclass(frozen=True, slots=True)
class SubsystemPolicy:
    """Per-subsystem resilience knobs."""

    failure_threshold: int = DEFAULT_FAILURE_THRESHOLD
    failure_window_s: float = DEFAULT_FAILURE_WINDOW_S
    open_duration_s: float = DEFAULT_OPEN_DURATION_S
    half_open_probes: int = DEFAULT_HALF_OPEN_PROBES
    recovery_backoff_s: float = DEFAULT_RECOVERY_BACKOFF_S
    max_recovery_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS
    quarantine_payload_kind: bool = False
    """When ``True`` the manager records the payload kind that
    triggered each failure (used by replay/recorder to quarantine a
    specific corrupted frame instead of restarting the whole
    subsystem)."""

    treat_cancelled_as_failure: bool = False
    """asyncio cancellations are usually structural, not failures.
    Replay/recorder set this to ``True`` to surface unexpected
    cancellations on long-running tasks."""


def _replay_policy() -> SubsystemPolicy:
    return SubsystemPolicy(
        failure_threshold=8,
        failure_window_s=15.0,
        open_duration_s=2.5,
        quarantine_payload_kind=True,
    )


def _websocket_policy() -> SubsystemPolicy:
    return SubsystemPolicy(
        failure_threshold=12,
        failure_window_s=10.0,
        open_duration_s=1.0,
        half_open_probes=4,
    )


def _reducer_policy() -> SubsystemPolicy:
    return SubsystemPolicy(
        failure_threshold=4,
        failure_window_s=5.0,
        open_duration_s=2.0,
    )


def _render_policy() -> SubsystemPolicy:
    return SubsystemPolicy(
        failure_threshold=6,
        failure_window_s=4.0,
        open_duration_s=1.0,
    )


def _recorder_policy() -> SubsystemPolicy:
    return SubsystemPolicy(
        failure_threshold=3,
        failure_window_s=30.0,
        open_duration_s=10.0,
        quarantine_payload_kind=True,
    )


@dataclass(frozen=True, slots=True)
class IsolationConfig:
    """Immutable resilience-manager configuration."""

    default_policy: SubsystemPolicy = field(default_factory=SubsystemPolicy)
    per_subsystem: dict[str, SubsystemPolicy] = field(
        default_factory=lambda: {
            "replay": _replay_policy(),
            "websocket": _websocket_policy(),
            "reducer": _reducer_policy(),
            "render": _render_policy(),
            "recorder": _recorder_policy(),
        },
    )
    """``subsystem_name → policy``. Subsystems not listed fall back
    to :attr:`default_policy`."""

    trace_capacity: int = DEFAULT_TRACE_CAPACITY
    enable_tracing: bool = False
    autorecover: bool = True
    """``True`` means closed breakers may transition back to
    ``half_open`` after the configured cooldown. ``False`` keeps
    them tripped until the operator explicitly closes them."""

    halt_on_critical_subsystem: bool = False
    """When a *critical* subsystem fails N times, the manager
    transitions the runtime to ``halt`` mode instead of merely
    ``emergency``. Operators that prefer to take a clean snapshot +
    crash explicitly set this to ``True``."""

    degraded_grace_s: float = 30.0
    """How long the manager waits with no new failures before
    leaving ``degraded`` mode."""


def default_config() -> IsolationConfig:
    return IsolationConfig()


def lean_config() -> IsolationConfig:
    return IsolationConfig(
        default_policy=SubsystemPolicy(
            failure_threshold=3,
            failure_window_s=5.0,
            open_duration_s=1.0,
            recovery_backoff_s=0.5,
        ),
        per_subsystem={
            "replay": SubsystemPolicy(
                failure_threshold=4,
                failure_window_s=5.0,
                open_duration_s=1.0,
                quarantine_payload_kind=True,
            ),
            "websocket": SubsystemPolicy(
                failure_threshold=6,
                failure_window_s=4.0,
                open_duration_s=0.5,
                half_open_probes=2,
            ),
            "reducer": SubsystemPolicy(
                failure_threshold=2,
                failure_window_s=2.0,
                open_duration_s=0.5,
            ),
            "render": SubsystemPolicy(
                failure_threshold=3,
                failure_window_s=2.0,
                open_duration_s=0.5,
            ),
            "recorder": SubsystemPolicy(
                failure_threshold=2,
                failure_window_s=10.0,
                open_duration_s=2.0,
                quarantine_payload_kind=True,
            ),
        },
        degraded_grace_s=10.0,
    )


def relaxed_config() -> IsolationConfig:
    return IsolationConfig(
        default_policy=SubsystemPolicy(
            failure_threshold=20,
            failure_window_s=120.0,
            open_duration_s=30.0,
            recovery_backoff_s=5.0,
            max_recovery_attempts=20,
        ),
        per_subsystem={
            "replay": SubsystemPolicy(
                failure_threshold=24,
                failure_window_s=120.0,
                open_duration_s=15.0,
                quarantine_payload_kind=True,
            ),
            "websocket": SubsystemPolicy(
                failure_threshold=40,
                failure_window_s=60.0,
                open_duration_s=10.0,
                half_open_probes=8,
            ),
            "reducer": SubsystemPolicy(
                failure_threshold=12,
                failure_window_s=60.0,
                open_duration_s=10.0,
            ),
            "render": SubsystemPolicy(
                failure_threshold=20,
                failure_window_s=30.0,
                open_duration_s=5.0,
            ),
            "recorder": SubsystemPolicy(
                failure_threshold=10,
                failure_window_s=300.0,
                open_duration_s=60.0,
                quarantine_payload_kind=True,
            ),
        },
        degraded_grace_s=120.0,
    )
