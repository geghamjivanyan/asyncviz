"""Seek request dispatch — routes intents into the engine.

The dispatch layer is the only public API the coordinator exposes
for accepting requests. It:

1. Allocates a monotonic ``request_id``.
2. Pushes onto the bounded queue (drop-oldest).
3. Updates the state holder to reflect "in flight".
4. Triggers the engine.
5. Updates the cursor + records metrics.
6. Returns a :class:`SeekResult`.

Coalescing happens here: an incoming request supersedes any older
queued ones, cancelling them outright.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable

from asyncviz.replay.runtime.seek.models.seek_request import (
    SeekRequest,
    SeekResult,
)
from asyncviz.replay.runtime.seek.models.seek_state import (
    SeekState,
    SeekStateSnapshot,
)
from asyncviz.replay.runtime.seek.replay_seek_backpressure import SeekQueue
from asyncviz.replay.runtime.seek.replay_seek_cursor import SeekCursorRuntime
from asyncviz.replay.runtime.seek.replay_seek_engine import (
    SeekEngine,
    SeekExecutionInputs,
)
from asyncviz.replay.runtime.seek.replay_seek_observability import (
    get_seek_metrics,
)
from asyncviz.replay.runtime.seek.replay_seek_state import SeekStateHolder
from asyncviz.replay.runtime.seek.replay_seek_tracing import record_seek_trace


class SeekDispatch:
    """Single entrypoint for routing seek requests."""

    __slots__ = (
        "_coalesce",
        "_cursor",
        "_engine",
        "_lock",
        "_queue",
        "_request_counter",
        "_state",
    )

    def __init__(
        self,
        *,
        engine: SeekEngine,
        state: SeekStateHolder,
        cursor: SeekCursorRuntime,
        queue_capacity: int = 32,
        coalesce_intermediate_scrubs: bool = True,
    ) -> None:
        self._engine = engine
        self._state = state
        self._cursor = cursor
        self._queue: SeekQueue[SeekRequest] = SeekQueue(capacity=queue_capacity)
        self._coalesce = coalesce_intermediate_scrubs
        self._request_counter = 0
        self._lock = threading.Lock()

    # ── id allocation ─────────────────────────────────────────────

    def allocate_request_id(self) -> int:
        with self._lock:
            self._request_counter += 1
            return self._request_counter

    # ── synchronous dispatch ──────────────────────────────────────

    def submit(self, request: SeekRequest, *, target_sequence: int) -> SeekResult:
        """Run a seek synchronously + return the result.

        Coalesces against any older queued request — older ones get
        cancelled before this one runs.
        """
        metrics = get_seek_metrics()
        evicted = self._queue.offer(request)
        if evicted is not None and self._coalesce:
            metrics.record_coordination_drop()
            metrics.record_cancelled()
            record_seek_trace(
                "seek-coalesced",
                f"dropped={evicted.request_id} replaced_by={request.request_id}",
            )

        # State holder: transition to RECONSTRUCTING.
        previous = self._state.snapshot
        self._state.transition_to(
            SeekStateSnapshot(
                state=SeekState.RECONSTRUCTING,
                in_flight_request_id=request.request_id,
                target_sequence=target_sequence,
                last_completed_sequence=previous.last_completed_sequence,
                pending_count=len(self._queue),
            ),
        )
        record_seek_trace(
            "seek-started",
            f"id={request.request_id} target={target_sequence}",
        )

        result = self._engine.execute(
            SeekExecutionInputs(
                target_sequence=target_sequence, request=request,
            ),
        )

        # Update cursor + state holder atomically.
        if result.error_detail:
            self._state.transition_to(
                SeekStateSnapshot(
                    state=SeekState.FAILED,
                    in_flight_request_id=0,
                    target_sequence=target_sequence,
                    last_completed_sequence=previous.last_completed_sequence,
                    pending_count=len(self._queue),
                    error_detail=result.error_detail,
                ),
            )
            record_seek_trace(
                "seek-failed", f"id={request.request_id} err={result.error_detail}",
            )
            return result

        self._cursor.set(
            self._cursor.cursor.advance(
                sequence=result.landed_sequence,
                monotonic_ns=result.landed_monotonic_ns,
                request_id=request.request_id,
            ),
        )
        self._state.transition_to(
            SeekStateSnapshot(
                state=SeekState.COMPLETED,
                in_flight_request_id=0,
                target_sequence=target_sequence,
                last_completed_sequence=result.landed_sequence,
                pending_count=len(self._queue),
            ),
        )
        record_seek_trace(
            "seek-completed",
            f"id={request.request_id} landed={result.landed_sequence}",
        )
        # Drain the request out of the queue now that it's complete.
        # (We could pop precisely; cheap to just consume one head.)
        if len(self._queue) > 0:
            self._queue.drain()
        return result

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    def queue_stats(self):
        return self._queue.stats()

    def cancel_pending(self) -> Iterable[int]:
        """Cancel everything in the queue. Returns the ids cancelled."""
        drained = self._queue.drain()
        return tuple(req.request_id for req in drained)
