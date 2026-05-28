"""Transition → segmentation-intent classification.

The state-store reducer chain emits :class:`StateChange` notifications
keyed by event type. The timeline engine needs a slightly different view:
"what should this transition do to the active span?". This module owns
that mapping so :class:`TimelineSegmentEngine` doesn't carry the dispatch
logic itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from asyncviz.runtime.events.models.enums import TaskState


class SegmentIntent(StrEnum):
    """What the engine should do with a transition.

    * ``CREATE``   — initialize the LifecycleSpan; no segment opened yet.
    * ``OPEN_RUN`` — start a new ``"run"`` segment, closing any open one.
    * ``OPEN_WAIT`` — start a new ``"wait"`` segment, closing any open one.
    * ``CLOSE_AND_FINALIZE`` — close the active segment, mark the task
      terminal.
    * ``IGNORE`` — no segmentation effect (unknown future states).
    """

    CREATE = "create"
    OPEN_RUN = "open_run"
    OPEN_WAIT = "open_wait"
    CLOSE_AND_FINALIZE = "close_and_finalize"
    IGNORE = "ignore"


@dataclass(frozen=True, slots=True)
class TransitionIntent:
    """Resolved decision for one transition."""

    intent: SegmentIntent
    target_state: TaskState


#: Source-of-truth mapping. Keyed on :class:`TaskState` (the *target* state
#: of the transition); the engine doesn't need to inspect the source state.
INTENT_BY_TARGET: dict[TaskState, SegmentIntent] = {
    TaskState.CREATED: SegmentIntent.CREATE,
    TaskState.RUNNING: SegmentIntent.OPEN_RUN,
    TaskState.WAITING: SegmentIntent.OPEN_WAIT,
    TaskState.COMPLETED: SegmentIntent.CLOSE_AND_FINALIZE,
    TaskState.CANCELLED: SegmentIntent.CLOSE_AND_FINALIZE,
    TaskState.FAILED: SegmentIntent.CLOSE_AND_FINALIZE,
}


def intent_for(target: TaskState) -> SegmentIntent:
    """Resolve the segmentation intent for a transition to ``target``."""
    return INTENT_BY_TARGET.get(target, SegmentIntent.IGNORE)


def is_terminal_intent(intent: SegmentIntent) -> bool:
    return intent is SegmentIntent.CLOSE_AND_FINALIZE
