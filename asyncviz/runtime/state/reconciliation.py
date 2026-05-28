"""Reconciliation policy.

Deciding whether an incoming event is fresh, stale, or a duplicate is
distinct from *applying* it. We separate them so tests can drive the
policy directly and so the store can swap policies for replay tools
without touching reducers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReconciliationDecision(StrEnum):
    """Outcome of :meth:`ReconciliationPolicy.evaluate`.

    * ``APPLY`` — fresh; reducer should run.
    * ``STALE`` — sequence already reflected in the store; suppress.
    * ``DUPLICATE`` — same ``event_id`` we already applied; suppress.
    """

    APPLY = "apply"
    STALE = "stale"
    DUPLICATE = "duplicate"


@dataclass(slots=True)
class ReconciliationPolicy:
    """Sequence-aware dedup and stale-event filter.

    The policy carries two pieces of state:

    * ``last_sequence`` — highest applied envelope sequence. Increments only
      on successful applies. Events with ``sequence <= last_sequence`` are
      stale.
    * ``seen_event_ids`` — bounded set of recently-applied event ids. The
      bound (``event_id_window``) keeps memory flat under steady-state
      churn while still catching transport duplicates.

    Replays *reset* both pieces via :meth:`reset_for_rebuild` so a recorded
    log can be replayed end-to-end without false stale rejections.
    """

    event_id_window: int = 4096
    _last_sequence: int = 0
    _seen_ids_set: set[str] | None = None
    _seen_ids_order: list[str] | None = None

    def __post_init__(self) -> None:
        if self.event_id_window <= 0:
            raise ValueError("event_id_window must be > 0")
        self._seen_ids_set = set()
        self._seen_ids_order = []

    @property
    def last_sequence(self) -> int:
        return self._last_sequence

    def evaluate(
        self,
        *,
        sequence: int | None,
        event_id: str,
    ) -> ReconciliationDecision:
        if event_id in (self._seen_ids_set or ()):
            return ReconciliationDecision.DUPLICATE
        if sequence is not None and sequence <= self._last_sequence:
            return ReconciliationDecision.STALE
        return ReconciliationDecision.APPLY

    def record_applied(self, *, sequence: int | None, event_id: str) -> None:
        """Mark a successful apply so future evaluations dedup correctly."""
        if sequence is not None and sequence > self._last_sequence:
            self._last_sequence = sequence
        assert self._seen_ids_set is not None
        assert self._seen_ids_order is not None
        self._seen_ids_set.add(event_id)
        self._seen_ids_order.append(event_id)
        if len(self._seen_ids_order) > self.event_id_window:
            evicted = self._seen_ids_order.pop(0)
            self._seen_ids_set.discard(evicted)

    def reset_for_rebuild(self) -> None:
        """Forget everything. Called at the start of :meth:`RuntimeStateStore.rebuild`."""
        self._last_sequence = 0
        assert self._seen_ids_set is not None
        assert self._seen_ids_order is not None
        self._seen_ids_set.clear()
        self._seen_ids_order.clear()
