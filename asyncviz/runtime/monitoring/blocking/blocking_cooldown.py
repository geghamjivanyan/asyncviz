"""Per-severity cooldown / deduplication policy.

Once the detector emits a violation event at severity X, it suppresses
subsequent X-or-lower events for ``cooldown_ns`` nanoseconds. This
prevents the dashboard from being flooded by a stream of identical
warnings during a sustained lag spike.

Cooldowns are *severity-aware*: a CRITICAL event clears the WARNING
cooldown so the dashboard always sees escalations even mid-cooldown.
Higher severities bypass lower-severity cooldowns.

Replay safety: the cooldown is driven by the *measurement's* monotonic
timestamp, not by ``time.monotonic_ns()`` reads. Identical inputs →
identical suppressions.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass

from asyncviz.runtime.monitoring.blocking.blocking_classifier import BlockingSeverity


@dataclass(frozen=True, slots=True)
class CooldownDecision:
    """Outcome of one cooldown check.

    ``suppressed`` → the caller should drop the event. ``remaining_ns``
    is the nanoseconds left before the suppression lifts (0 when not
    suppressed).
    """

    severity: BlockingSeverity
    suppressed: bool
    remaining_ns: int


class BlockingCooldownPolicy:
    """Per-severity cooldown window in monotonic nanoseconds.

    Construct with the cooldown duration per severity. ``0`` (default
    for ``NONE``) means "no cooldown — every event passes".

    Defaults:
      * WARNING  → 250ms — chatter protection.
      * CRITICAL → 500ms — still rate-limited but tighter.
      * FREEZE   → 0   — every freeze must surface; user impact is high.
    """

    DEFAULT_WARNING_COOLDOWN_NS: int = 250_000_000
    DEFAULT_CRITICAL_COOLDOWN_NS: int = 500_000_000
    DEFAULT_FREEZE_COOLDOWN_NS: int = 0

    __slots__ = ("_cooldowns_ns", "_last_emit_ns", "_lock")

    def __init__(
        self,
        *,
        warning_ns: int = DEFAULT_WARNING_COOLDOWN_NS,
        critical_ns: int = DEFAULT_CRITICAL_COOLDOWN_NS,
        freeze_ns: int = DEFAULT_FREEZE_COOLDOWN_NS,
    ) -> None:
        for name, value in (
            ("warning_ns", warning_ns),
            ("critical_ns", critical_ns),
            ("freeze_ns", freeze_ns),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0 (got {value})")
        self._lock = threading.Lock()
        self._cooldowns_ns: dict[BlockingSeverity, int] = {
            BlockingSeverity.NONE: 0,
            BlockingSeverity.WARNING: warning_ns,
            BlockingSeverity.CRITICAL: critical_ns,
            BlockingSeverity.FREEZE: freeze_ns,
        }
        self._last_emit_ns: dict[BlockingSeverity, int] = dict.fromkeys(BlockingSeverity, -(10**12))

    def cooldown_for(self, severity: BlockingSeverity) -> int:
        return self._cooldowns_ns[severity]

    def reset(self) -> None:
        with self._lock:
            for sev in BlockingSeverity:
                self._last_emit_ns[sev] = -(10**12)

    def configure(
        self,
        *,
        warning_ns: int | None = None,
        critical_ns: int | None = None,
        freeze_ns: int | None = None,
    ) -> None:
        """Swap cooldowns. Counters (``_last_emit_ns``) preserved."""
        with self._lock:
            if warning_ns is not None:
                self._cooldowns_ns[BlockingSeverity.WARNING] = warning_ns
            if critical_ns is not None:
                self._cooldowns_ns[BlockingSeverity.CRITICAL] = critical_ns
            if freeze_ns is not None:
                self._cooldowns_ns[BlockingSeverity.FREEZE] = freeze_ns

    def check_and_record(
        self,
        severity: BlockingSeverity,
        *,
        now_ns: int,
    ) -> CooldownDecision:
        """Decide whether to suppress an emission of ``severity`` at ``now_ns``.

        Records the emission timestamp when the decision is "accept",
        which is the common case. Returns a :class:`CooldownDecision`
        so callers can update self-metrics consistently.

        Same-or-lower severity events are subject to suppression;
        higher-severity events bypass.
        """
        if severity is BlockingSeverity.NONE:
            return CooldownDecision(severity=severity, suppressed=False, remaining_ns=0)
        with self._lock:
            cooldown_ns = self._cooldowns_ns[severity]
            if cooldown_ns <= 0:
                self._last_emit_ns[severity] = now_ns
                return CooldownDecision(severity=severity, suppressed=False, remaining_ns=0)
            since_last = now_ns - self._last_emit_ns[severity]
            if since_last >= cooldown_ns:
                self._last_emit_ns[severity] = now_ns
                return CooldownDecision(severity=severity, suppressed=False, remaining_ns=0)
            return CooldownDecision(
                severity=severity,
                suppressed=True,
                remaining_ns=cooldown_ns - since_last,
            )

    def force_record(self, severity: BlockingSeverity, *, now_ns: int) -> None:
        """Stamp ``now_ns`` as the last emission time for ``severity``.

        Used after a successful emit when the caller bypassed
        :meth:`check_and_record` (e.g. escalation path).
        """
        if severity is BlockingSeverity.NONE:
            return
        with self._lock:
            self._last_emit_ns[severity] = now_ns

    def to_dict(self) -> dict[str, int]:
        with self._lock:
            return {sev.name: ns for sev, ns in self._cooldowns_ns.items()}
