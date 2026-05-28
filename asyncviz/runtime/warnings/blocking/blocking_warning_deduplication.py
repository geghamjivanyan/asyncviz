"""Per-transition deduplication for warning emission.

The emitter publishes one transition event per lifecycle move
(``opened`` / ``escalated`` / ``active`` / ``recovered`` / ``expired``).
Without dedup, the ``active`` transition can fire on every refresh,
producing a flood of identical events as a freeze stretches across
many samples.

Dedup is keyed by ``(group_id, transition)``. Same key within the
configured cooldown → suppressed. Different transition (e.g. an
escalation arriving during an active cooldown) → accepted.

Replay-safe: the cooldown is driven by the *measurement's*
``monotonic_ns``, never by the real-time clock. Identical input
streams produce identical suppressions.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import ClassVar

DEFAULT_OPENED_COOLDOWN_NS: int = 0  # opens always fire
DEFAULT_ESCALATED_COOLDOWN_NS: int = 0  # escalations always fire
DEFAULT_ACTIVE_COOLDOWN_NS: int = 250_000_000  # 250 ms between refreshes
DEFAULT_RECOVERED_COOLDOWN_NS: int = 0  # recoveries always fire
DEFAULT_EXPIRED_COOLDOWN_NS: int = 0  # expirations always fire


@dataclass(frozen=True, slots=True)
class DedupDecision:
    suppressed: bool
    remaining_ns: int
    reason: str


class TransitionDeduplicator:
    """Per-(group, transition) cooldown.

    Cooldowns are configured per *transition kind*, not per group, so
    ``active`` events get rate-limited but ``escalated`` events get
    through even mid-cooldown.
    """

    DEFAULTS: ClassVar[dict[str, int]] = {
        "opened": DEFAULT_OPENED_COOLDOWN_NS,
        "escalated": DEFAULT_ESCALATED_COOLDOWN_NS,
        "active": DEFAULT_ACTIVE_COOLDOWN_NS,
        "recovered": DEFAULT_RECOVERED_COOLDOWN_NS,
        "expired": DEFAULT_EXPIRED_COOLDOWN_NS,
    }

    __slots__ = ("_cooldowns_ns", "_last_emit", "_lock")

    def __init__(
        self,
        *,
        opened_ns: int = DEFAULT_OPENED_COOLDOWN_NS,
        escalated_ns: int = DEFAULT_ESCALATED_COOLDOWN_NS,
        active_ns: int = DEFAULT_ACTIVE_COOLDOWN_NS,
        recovered_ns: int = DEFAULT_RECOVERED_COOLDOWN_NS,
        expired_ns: int = DEFAULT_EXPIRED_COOLDOWN_NS,
    ) -> None:
        for name, value in (
            ("opened_ns", opened_ns),
            ("escalated_ns", escalated_ns),
            ("active_ns", active_ns),
            ("recovered_ns", recovered_ns),
            ("expired_ns", expired_ns),
        ):
            if value < 0:
                raise ValueError(f"{name} must be >= 0 (got {value})")
        self._cooldowns_ns: dict[str, int] = {
            "opened": opened_ns,
            "escalated": escalated_ns,
            "active": active_ns,
            "recovered": recovered_ns,
            "expired": expired_ns,
        }
        # Keyed by ``(group_id, transition)``.
        self._last_emit: dict[tuple[str, str], int] = {}
        self._lock = threading.Lock()

    def cooldown_for(self, transition: str) -> int:
        return self._cooldowns_ns.get(transition, 0)

    def reset(self) -> None:
        with self._lock:
            self._last_emit.clear()

    def forget_group(self, group_id: str) -> None:
        with self._lock:
            for key in list(self._last_emit.keys()):
                if key[0] == group_id:
                    self._last_emit.pop(key, None)

    def check_and_record(
        self,
        *,
        group_id: str,
        transition: str,
        now_ns: int,
    ) -> DedupDecision:
        cooldown = self._cooldowns_ns.get(transition, 0)
        if cooldown <= 0:
            with self._lock:
                self._last_emit[(group_id, transition)] = now_ns
            return DedupDecision(suppressed=False, remaining_ns=0, reason="no_cooldown")
        with self._lock:
            last = self._last_emit.get((group_id, transition))
            if last is None or (now_ns - last) >= cooldown:
                self._last_emit[(group_id, transition)] = now_ns
                return DedupDecision(suppressed=False, remaining_ns=0, reason="elapsed")
            remaining = cooldown - (now_ns - last)
            return DedupDecision(suppressed=True, remaining_ns=remaining, reason="within_cooldown")

    def to_dict(self) -> dict[str, int]:
        return dict(self._cooldowns_ns)
