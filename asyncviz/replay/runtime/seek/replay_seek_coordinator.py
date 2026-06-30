"""Canonical replay seek coordinator.

Composes every piece into one public API:

    seek_coord = ReplaySeekCoordinator(
        loader=engine.loader,
        state_store=engine.state_store,
        cursor=engine_cursor_runtime,
        clock=engine.clock,
        checkpoints=engine.checkpoints,
        playback=playback_coordinator,  # optional
    )
    result = seek_coord.seek_to_sequence(1000)
    result = seek_coord.seek_to_timestamp(50_000_000)
    result = seek_coord.seek_relative(+50)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from asyncviz.replay.loading import ReplayEventLoader
from asyncviz.replay.runtime.replay_checkpoint_runtime import CheckpointRuntime
from asyncviz.replay.runtime.replay_clock import ReplayClock
from asyncviz.replay.runtime.replay_cursor_runtime import CursorRuntime
from asyncviz.replay.runtime.replay_reducers import ReducerRegistry
from asyncviz.replay.runtime.replay_scheduler import ReplayScheduler
from asyncviz.replay.runtime.replay_seek_runtime import ReplaySeekRuntime
from asyncviz.replay.runtime.replay_state_store import ReplayStateStore
from asyncviz.replay.runtime.seek.models.seek_cursor import SeekCursor
from asyncviz.replay.runtime.seek.models.seek_request import (
    SeekIntent,
    SeekRequest,
    SeekResult,
)
from asyncviz.replay.runtime.seek.models.seek_state import (
    SeekState,
    SeekStateSnapshot,
)
from asyncviz.replay.runtime.seek.replay_seek_cache import SeekCache
from asyncviz.replay.runtime.seek.replay_seek_clock import SeekClockCoordinator
from asyncviz.replay.runtime.seek.replay_seek_configuration import (
    ReplaySeekConfig,
)
from asyncviz.replay.runtime.seek.replay_seek_cursor import SeekCursorRuntime
from asyncviz.replay.runtime.seek.replay_seek_diagnostics import (
    SeekDiagnostics,
    build_seek_diagnostics,
)
from asyncviz.replay.runtime.seek.replay_seek_dispatch import SeekDispatch
from asyncviz.replay.runtime.seek.replay_seek_engine import SeekEngine
from asyncviz.replay.runtime.seek.replay_seek_integrity import (
    SeekIntegrityError,
    check_seek_result,
)
from asyncviz.replay.runtime.seek.replay_seek_observability import (
    get_seek_metrics,
)
from asyncviz.replay.runtime.seek.replay_seek_reconstruction import (
    ReconstructionPipeline,
)
from asyncviz.replay.runtime.seek.replay_seek_scheduler import (
    SeekSchedulerCoordinator,
)
from asyncviz.replay.runtime.seek.replay_seek_state import SeekStateHolder
from asyncviz.replay.runtime.seek.replay_seek_tracing import record_seek_trace
from asyncviz.replay.runtime.seek.utils.targets import (
    MarkerResolver,
    resolve_target_sequence,
)

if TYPE_CHECKING:
    from asyncviz.replay.runtime.control import ReplayPlaybackCoordinator


PauseHook = Callable[[], None]
"""Pluggable pause-before-seek hook. The coordinator calls it
synchronously before reconstruction starts."""

ResumeHook = Callable[[], None]


class ReplaySeekCoordinator:
    """Top-level replay-seek façade."""

    __slots__ = (
        "_cache",
        "_clock",
        "_config",
        "_cursor",
        "_dispatch",
        "_engine",
        "_engine_cursor",
        "_loader",
        "_marker_resolver",
        "_pause_hook",
        "_pipeline",
        "_resume_hook",
        "_scheduler",
        "_seek_runtime",
        "_state",
        "_state_holder",
    )

    def __init__(
        self,
        *,
        loader: ReplayEventLoader,
        state_store: ReplayStateStore,
        engine_cursor: CursorRuntime,
        clock: ReplayClock,
        scheduler: ReplayScheduler,
        checkpoints: CheckpointRuntime,
        reducers: ReducerRegistry,
        config: ReplaySeekConfig | None = None,
        playback: ReplayPlaybackCoordinator | None = None,
        marker_resolver: MarkerResolver | None = None,
    ) -> None:
        cfg = config or ReplaySeekConfig()
        self._config = cfg
        self._loader = loader
        self._state = state_store
        self._engine_cursor = engine_cursor
        self._marker_resolver = marker_resolver

        # Cache + reconstruction pipeline.
        self._cache = SeekCache(capacity=cfg.cache_capacity)
        self._seek_runtime = ReplaySeekRuntime(
            loader=loader,
            reducers=reducers,
            state_store=state_store,
            cursor=engine_cursor,
            clock=clock,
            checkpoints=checkpoints,
        )
        self._pipeline = ReconstructionPipeline(
            seek_runtime=self._seek_runtime,
            checkpoints=checkpoints,
            cache=self._cache,
        )
        self._clock = SeekClockCoordinator(clock)
        self._scheduler = SeekSchedulerCoordinator(scheduler=scheduler)
        self._cursor = SeekCursorRuntime()
        self._state_holder = SeekStateHolder()
        self._engine = SeekEngine(
            pipeline=self._pipeline,
            state_store=state_store,
            cursor=engine_cursor,
            clock=self._clock,
            checkpoints=checkpoints,
            cache_results=cfg.cache_capacity > 0,
            record_checkpoint=cfg.record_checkpoint_on_seek,
        )
        self._dispatch = SeekDispatch(
            engine=self._engine,
            state=self._state_holder,
            cursor=self._cursor,
            queue_capacity=cfg.queue_capacity,
            coalesce_intermediate_scrubs=cfg.coalesce_intermediate_scrubs,
        )

        # Pause/resume hooks (default to playback coordinator if
        # supplied, otherwise no-op).
        if playback is not None and cfg.pause_before_seek:
            self._pause_hook = lambda: playback.request_pause(
                trigger="immediate",
                reason="seek",
            )
            self._resume_hook = (
                (lambda: playback.request_resume(reason="seek-complete"))
                if cfg.resume_after_seek
                else None
            )
        else:
            self._pause_hook = None
            self._resume_hook = None

    # ── accessors ─────────────────────────────────────────────────

    @property
    def cursor(self) -> SeekCursor:
        return self._cursor.cursor

    @property
    def state(self) -> SeekStateSnapshot:
        return self._state_holder.snapshot

    @property
    def cache(self) -> SeekCache:
        return self._cache

    @property
    def config(self) -> ReplaySeekConfig:
        return self._config

    # ── public seek API ───────────────────────────────────────────

    def seek_to_sequence(self, sequence: int, *, reason: str = "") -> SeekResult:
        return self._dispatch_intent(
            SeekIntent.to_sequence(sequence),
            reason=reason,
        )

    def seek_to_timestamp(
        self,
        monotonic_ns: int,
        *,
        reason: str = "",
    ) -> SeekResult:
        return self._dispatch_intent(
            SeekIntent.to_timestamp(monotonic_ns),
            reason=reason,
        )

    def seek_to_marker(self, marker_id: str, *, reason: str = "") -> SeekResult:
        return self._dispatch_intent(
            SeekIntent.to_marker(marker_id),
            reason=reason,
        )

    def seek_relative(self, delta: int, *, reason: str = "") -> SeekResult:
        return self._dispatch_intent(SeekIntent.relative(delta), reason=reason)

    def seek(self, intent: SeekIntent, *, reason: str = "") -> SeekResult:
        return self._dispatch_intent(intent, reason=reason)

    def rebuild_at_cursor(self) -> SeekResult:
        """Re-reconstruct state at the most recent landing sequence —
        used by replay-state reset flows."""
        return self.seek_to_sequence(self._cursor.cursor.last_seek_sequence)

    # ── internals ─────────────────────────────────────────────────

    def _dispatch_intent(self, intent: SeekIntent, *, reason: str) -> SeekResult:
        metrics = get_seek_metrics()
        metrics.record_requested()
        record_seek_trace("seek-requested", f"kind={intent.kind}")

        request = SeekRequest(
            request_id=self._dispatch.allocate_request_id(),
            intent=intent,
            strategy=self._config.strategy,
            reason=reason,
        )
        try:
            target_sequence = resolve_target_sequence(
                intent,
                loader=self._loader,
                current_cursor_sequence=(self._cursor.cursor.last_seek_sequence),
                marker_resolver=self._marker_resolver,
            )
        except Exception as exc:
            metrics.record_failed()
            record_seek_trace("seek-failed", f"resolve={exc}")
            self._state_holder.transition_to(
                SeekStateSnapshot(
                    state=SeekState.FAILED,
                    in_flight_request_id=request.request_id,
                    target_sequence=0,
                    last_completed_sequence=self._cursor.cursor.last_seek_sequence,
                    error_detail=str(exc),
                ),
            )
            return SeekResult(
                request_id=request.request_id,
                target_sequence=0,
                landed_sequence=0,
                landed_monotonic_ns=0,
                used_cache=False,
                used_checkpoint=False,
                used_snapshot=False,
                frames_replayed=0,
                latency_ns=0,
                error_detail=str(exc),
            )

        # Pause hook before reconstruction.
        if self._pause_hook is not None:
            self._pause_hook()

        previous_monotonic_ns = self._cursor.cursor.last_seek_monotonic_ns
        result = self._dispatch.submit(
            request,
            target_sequence=target_sequence,
        )

        # Integrity validation.
        if not result.error_detail and self._config.verify_integrity_on_seek:
            violation = check_seek_result(
                target_sequence=target_sequence,
                result=result,
                state=self._state.state,
                previous_monotonic_ns=previous_monotonic_ns,
                strategy=self._config.strategy,
            )
            if violation is not None:
                metrics.record_integrity_violation()
                record_seek_trace(
                    "integrity-violation",
                    f"{violation.kind}: {violation.detail}",
                )
                if self._config.strategy == "exact_only":
                    raise SeekIntegrityError(violation.detail)

        if self._resume_hook is not None:
            self._resume_hook()
        return result

    # ── diagnostics ───────────────────────────────────────────────

    def diagnostics(self, *, trace_limit: int = 32) -> SeekDiagnostics:
        return build_seek_diagnostics(
            self._state_holder.snapshot,
            self._cache.stats(),
            self._dispatch.queue_stats(),
            trace_limit=trace_limit,
        )
