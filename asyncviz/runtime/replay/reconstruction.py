"""Reconstruction helpers — replay frames back into subsystems."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from asyncviz.runtime.events.models import from_dict
from asyncviz.runtime.replay.frames import ReplayFrame

if TYPE_CHECKING:
    from asyncviz.runtime.metrics import RuntimeMetricsAggregator
    from asyncviz.runtime.state import RuntimeStateStore
    from asyncviz.runtime.warnings import RuntimeWarningManager


def replay_into_state_store(
    frames: Iterable[ReplayFrame],
    store: RuntimeStateStore,
) -> int:
    """Replay frames into a (cleared) :class:`RuntimeStateStore`.

    Returns the count of events successfully applied. The store is reset
    via :meth:`RuntimeStateStore.rebuild`; pass an empty iterable to just
    reset the store without replaying anything.
    """
    typed = [(from_dict(f.payload), f.sequence) for f in frames]

    # ``rebuild`` accepts an iterable of either ``RuntimeEvent`` or
    # ``QueuedEvent``; we synthesize ``QueuedEvent``s so the sequence rides
    # alongside the event through the reducer chain.
    from asyncviz.runtime.queue import QueuedEvent

    queued = [QueuedEvent(sequence=seq, event=event) for event, seq in typed]
    return store.rebuild(queued)


def replay_into_metrics(
    frames: Iterable[ReplayFrame],
    aggregator: RuntimeMetricsAggregator,
) -> int:
    """Reset and replay frames into a :class:`RuntimeMetricsAggregator`."""
    events_with_sequences = [(from_dict(f.payload), f.sequence) for f in frames]
    return aggregator.rebuild(events_with_sequences)


def replay_into_warning_manager(
    frames: Iterable[ReplayFrame],
    manager: RuntimeWarningManager,
) -> int:
    """Reset and replay frames into a :class:`RuntimeWarningManager`."""
    events_with_sequences = [(from_dict(f.payload), f.sequence) for f in frames]
    return manager.rebuild(events_with_sequences)
