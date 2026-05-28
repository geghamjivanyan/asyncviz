"""Replay-aware handshake protocol.

Pure helpers that decide what to send during the initial frames of a new
connection. The :class:`WebSocketGateway` owns the I/O; this module
makes the decisions.

The handshake protocol:

1. Client connects with optional ``?since_sequence=N`` query param.
2. Gateway asks the replay buffer for ``replay_since(N, with_checkpoint=True)``.
3. If retention covers the gap → stream the retained frames with their
   original sequence numbers. No snapshot needed.
4. Otherwise → send a fresh :class:`runtime_snapshot` envelope as the
   baseline. Optional checkpoint metadata rides alongside.
5. Transition to live streaming.

Step 3 is replay-deterministic because the buffer captured the same
events the broadcast bridge originally sent. Step 4 is the recovery
path: the snapshot is the source of truth at its `last_sequence`, and
subsequent live frames apply on top.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from asyncviz.runtime.replay import EventReplayBuffer, ReplayBatchModel


class HandshakeMode(StrEnum):
    """What the gateway should do on this handshake."""

    LIVE_ONLY = "live_only"  # no replay requested; just stream live
    REPLAY = "replay"  # retention covers the gap; stream it
    SNAPSHOT_FALLBACK = "snapshot"  # miss; send full snapshot + (optional) checkpoint


@dataclass(frozen=True, slots=True)
class HandshakeDecision:
    """Resolved plan for one handshake.

    Carries the :class:`ReplayBatchModel` when applicable so the gateway
    doesn't have to re-query the buffer. ``last_sequence_sent`` is the
    cursor the session should advance to *before* live streaming begins.
    """

    mode: HandshakeMode
    requested_since: int
    last_sequence_sent: int
    replay: ReplayBatchModel | None
    needs_snapshot: bool


def evaluate_handshake(
    *,
    buffer: EventReplayBuffer | None,
    since_sequence: int,
    bridge_current_sequence: int,
) -> HandshakeDecision:
    """Decide which handshake mode applies to the request."""
    if since_sequence <= 0:
        # Fresh connect — always start with a snapshot baseline.
        return HandshakeDecision(
            mode=HandshakeMode.LIVE_ONLY,
            requested_since=since_sequence,
            last_sequence_sent=bridge_current_sequence,
            replay=None,
            needs_snapshot=True,
        )

    if buffer is None:
        # No replay buffer wired — fall back to snapshot.
        return HandshakeDecision(
            mode=HandshakeMode.SNAPSHOT_FALLBACK,
            requested_since=since_sequence,
            last_sequence_sent=bridge_current_sequence,
            replay=None,
            needs_snapshot=True,
        )

    batch = buffer.replay_since(since_sequence, with_checkpoint=True)
    if batch.window.hit:
        last_in_batch = batch.window.frames[-1].sequence if batch.window.frames else since_sequence
        return HandshakeDecision(
            mode=HandshakeMode.REPLAY,
            requested_since=since_sequence,
            last_sequence_sent=last_in_batch,
            replay=batch,
            needs_snapshot=False,
        )

    return HandshakeDecision(
        mode=HandshakeMode.SNAPSHOT_FALLBACK,
        requested_since=since_sequence,
        last_sequence_sent=bridge_current_sequence,
        replay=batch,  # contains checkpoint if available
        needs_snapshot=True,
    )
