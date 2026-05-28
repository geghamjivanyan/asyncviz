"""Speed-change request dispatch.

Hands a :class:`SpeedChangeRequest` to the coordination layer +
manages the bounded queue + coalescing. Synchronous — the actual
clock mutation is fast enough that async barriers would add more
overhead than they save.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable

from asyncviz.replay.runtime.speed.models.speed_phase import (
    SpeedPhase,
    SpeedPhaseSnapshot,
)
from asyncviz.replay.runtime.speed.models.speed_request import (
    SpeedChangeRequest,
    SpeedChangeResult,
)
from asyncviz.replay.runtime.speed.replay_speed_backpressure import SpeedQueue
from asyncviz.replay.runtime.speed.replay_speed_clock import (
    SpeedClockCoordinator,
)
from asyncviz.replay.runtime.speed.replay_speed_integrity import (
    SpeedIntegrityError,
    check_transition,
)
from asyncviz.replay.runtime.speed.replay_speed_limits import (
    ClampVerdict,
    clamp_speed,
)
from asyncviz.replay.runtime.speed.replay_speed_observability import (
    get_speed_metrics,
)
from asyncviz.replay.runtime.speed.replay_speed_state import SpeedStateHolder
from asyncviz.replay.runtime.speed.replay_speed_tracing import (
    record_speed_trace,
)
from asyncviz.replay.runtime.speed.replay_speed_transition import (
    SpeedTransitionEngine,
)


class SpeedDispatch:
    """Routes requests through the transition engine."""

    __slots__ = (
        "_clock",
        "_coalesce",
        "_invalid_policy",
        "_lock",
        "_max_speed",
        "_min_speed",
        "_queue",
        "_request_counter",
        "_state",
        "_strict_integrity",
        "_transition_engine",
    )

    def __init__(
        self,
        *,
        clock: SpeedClockCoordinator,
        transition_engine: SpeedTransitionEngine,
        state: SpeedStateHolder,
        min_speed: float,
        max_speed: float,
        queue_capacity: int = 16,
        coalesce_repeated_requests: bool = True,
        invalid_policy: str = "clamp",
        strict_integrity: bool = False,
    ) -> None:
        self._clock = clock
        self._transition_engine = transition_engine
        self._state = state
        self._min_speed = min_speed
        self._max_speed = max_speed
        self._queue: SpeedQueue[SpeedChangeRequest] = SpeedQueue(
            capacity=queue_capacity,
        )
        self._coalesce = coalesce_repeated_requests
        self._invalid_policy = invalid_policy
        self._strict_integrity = strict_integrity
        self._request_counter = 0
        self._lock = threading.Lock()

    def allocate_request_id(self) -> int:
        with self._lock:
            self._request_counter += 1
            return self._request_counter

    def submit(self, request: SpeedChangeRequest) -> SpeedChangeResult:
        """Process a request synchronously + return the result."""
        started_ns = time.monotonic_ns()
        metrics = get_speed_metrics()
        previous_speed = self._clock.current_speed

        # Validation + clamp.
        verdict: ClampVerdict = clamp_speed(
            request.target_speed,
            min_speed=self._min_speed,
            max_speed=self._max_speed,
        )
        if not verdict.accepted:
            metrics.record_invalid_speed()
            record_speed_trace(
                "speed-rejected", f"id={request.request_id} {verdict.reason}",
            )
            if self._invalid_policy == "reject":
                self._state.transition_to(
                    SpeedPhaseSnapshot(
                        phase=SpeedPhase.REJECTED,
                        in_flight_request_id=0,
                        target_speed=request.target_speed,
                        current_speed=previous_speed,
                        last_completed_speed=previous_speed,
                        error_detail=verdict.reason,
                    ),
                )
                metrics.record_rejected()
                return SpeedChangeResult(
                    request_id=request.request_id,
                    requested_speed=verdict.requested,
                    applied_speed=previous_speed,
                    previous_speed=previous_speed,
                    coalesced=False,
                    rejected=True,
                    latency_ns=time.monotonic_ns() - started_ns,
                    clamped=False,
                    error_detail=verdict.reason,
                )
            # ``clamp`` policy — fall through with the resolved
            # value (which is NaN for non-numeric inputs).
            # Reject silently when even clamp can't recover.
            self._state.transition_to(
                SpeedPhaseSnapshot(
                    phase=SpeedPhase.REJECTED,
                    in_flight_request_id=0,
                    target_speed=request.target_speed,
                    current_speed=previous_speed,
                    last_completed_speed=previous_speed,
                    error_detail=verdict.reason,
                ),
            )
            metrics.record_rejected()
            return SpeedChangeResult(
                request_id=request.request_id,
                requested_speed=verdict.requested,
                applied_speed=previous_speed,
                previous_speed=previous_speed,
                coalesced=False,
                rejected=True,
                latency_ns=time.monotonic_ns() - started_ns,
                clamped=False,
                error_detail=verdict.reason,
            )

        # Coalesce against the most recent applied speed.
        if self._coalesce and abs(verdict.resolved - previous_speed) < 1e-9:
            metrics.record_coalesced()
            record_speed_trace(
                "speed-coalesced",
                f"id={request.request_id} speed={verdict.resolved}",
            )
            self._state.transition_to(
                SpeedPhaseSnapshot(
                    phase=SpeedPhase.COALESCED,
                    in_flight_request_id=0,
                    target_speed=verdict.resolved,
                    current_speed=previous_speed,
                    last_completed_speed=previous_speed,
                ),
            )
            return SpeedChangeResult(
                request_id=request.request_id,
                requested_speed=verdict.requested,
                applied_speed=previous_speed,
                previous_speed=previous_speed,
                coalesced=True,
                rejected=False,
                latency_ns=time.monotonic_ns() - started_ns,
                clamped=verdict.clamped,
            )

        # Enqueue + drop older requests via coalesce semantics.
        evicted = self._queue.offer(request)
        if evicted is not None:
            metrics.record_coordination_drop()
            record_speed_trace(
                "speed-coordination-drop",
                f"dropped={evicted.request_id} replaced_by={request.request_id}",
            )

        # Transition to APPLYING.
        self._state.transition_to(
            SpeedPhaseSnapshot(
                phase=SpeedPhase.APPLYING,
                in_flight_request_id=request.request_id,
                target_speed=verdict.resolved,
                current_speed=previous_speed,
                last_completed_speed=previous_speed,
            ),
        )

        if verdict.clamped:
            metrics.record_clamped()
            record_speed_trace(
                "speed-clamped",
                f"requested={verdict.requested} resolved={verdict.resolved}",
            )

        previous_anchor_virtual_ns = self._clock.anchor.virtual_ns
        transition = self._transition_engine.apply(
            request=request, resolved_speed=verdict.resolved,
        )

        # Integrity check.
        violation = check_transition(
            transition=transition,
            observed_speed=self._clock.current_speed,
            previous_virtual_ns=previous_anchor_virtual_ns,
            min_speed=self._min_speed,
            max_speed=self._max_speed,
        )
        if violation is not None:
            metrics.record_integrity_violation()
            record_speed_trace(
                "speed-integrity-violation",
                f"{violation.kind}: {violation.detail}",
            )
            if self._strict_integrity:
                raise SpeedIntegrityError(violation.detail)

        # Final state + history.
        self._state.record_transition(transition)
        self._state.transition_to(
            SpeedPhaseSnapshot(
                phase=SpeedPhase.APPLIED,
                in_flight_request_id=0,
                target_speed=verdict.resolved,
                current_speed=transition.new_speed,
                last_completed_speed=transition.new_speed,
            ),
        )
        latency_ns = time.monotonic_ns() - started_ns
        metrics.record_applied(latency_ns)
        metrics.record_transition()
        record_speed_trace(
            "speed-applied",
            f"id={request.request_id} from={previous_speed} to={transition.new_speed}",
        )

        # Drain the queue head — the engine ran synchronously, so
        # leaving stale items in the buffer would be misleading.
        if len(self._queue) > 0:
            self._queue.drain()

        return SpeedChangeResult(
            request_id=request.request_id,
            requested_speed=verdict.requested,
            applied_speed=transition.new_speed,
            previous_speed=previous_speed,
            coalesced=False,
            rejected=False,
            latency_ns=latency_ns,
            clamped=verdict.clamped,
        )

    @property
    def pending_count(self) -> int:
        return len(self._queue)

    def queue_stats(self):
        return self._queue.stats()

    def cancel_pending(self) -> Iterable[int]:
        drained = self._queue.drain()
        return tuple(req.request_id for req in drained)
