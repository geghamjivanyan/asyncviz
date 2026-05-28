from __future__ import annotations

from enum import StrEnum


class OverflowStrategy(StrEnum):
    """Policy applied when the queue is at capacity.

    * ``DROP_OLDEST`` — discard the head (oldest unconsumed event). New events
      always make it onto the queue; subscribers lose visibility into the
      oldest pending event. This is the default — for a real-time dashboard,
      "freshest events win" is the right trade.
    * ``DROP_NEWEST`` — discard the publish currently being attempted. The
      queue tail is preserved; producer learns of the drop synchronously via
      metrics, never via an exception.
    * ``FAIL_FAST``  — raise :class:`EventQueueOverflowError` so the
      publisher decides. Intended for tests and unusual producers, *not* for
      the instrumentation hot path.
    """

    DROP_OLDEST = "drop_oldest"
    DROP_NEWEST = "drop_newest"
    FAIL_FAST = "fail_fast"


#: Default for the dashboard runtime. Chosen so the freshest events always
#: reach the UI even when subscribers stall — a stalled consumer can't poison
#: instrumentation by causing visible misses on the *current* state.
DEFAULT_OVERFLOW_STRATEGY: OverflowStrategy = OverflowStrategy.DROP_OLDEST
