"""Backpressure primitives — bounded outbound queue per session.

Today the gateway uses these primarily to count slow-client events. A
future flow-control layer can promote them to active throttling.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Default per-session outbound queue cap (number of envelopes).
DEFAULT_OUTBOUND_QUEUE_DEPTH: int = 512


@dataclass(frozen=True, slots=True)
class BackpressurePolicy:
    """Configuration knobs.

    ``max_queue_depth`` is the max number of in-flight envelopes a single
    session can buffer before the gateway evicts it. Setting this small
    helps protect the broadcast pump from one slow client; setting it
    too small drops normal traffic for clients on flaky networks.
    """

    max_queue_depth: int = DEFAULT_OUTBOUND_QUEUE_DEPTH
    drop_oldest: bool = False


def is_overflowed(*, queue_depth: int, policy: BackpressurePolicy) -> bool:
    return queue_depth >= policy.max_queue_depth
