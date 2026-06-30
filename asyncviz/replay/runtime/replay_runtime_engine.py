"""Canonical replay runtime engine.

Top-level façade that wires together every layer:

* :class:`ReplayEventLoader` — source of frames + snapshots
* :class:`ReplayClock` — virtual-time anchor
* :class:`ReplayScheduler` — per-frame delay computation
* :class:`PauseController` + :class:`SpeedController` — playback knobs
* :class:`ReducerRegistry` + :class:`ReplayStateStore` — state evolution
* :class:`CheckpointRuntime` + :class:`SnapshotRuntime` — fast seek
* :class:`ReplayEventRouter` + :class:`ReplayWebsocketBridge` — fan-out
* :class:`ReplayDispatch` — the single hot dispatch path
* :class:`ReplaySeekRuntime` — coordinated seek
* :class:`PlaybackController` — async loop

The engine exposes the small ergonomic surface that callers need:

    engine = ReplayRuntimeEngine(loader=loader, sink=sink)
    await engine.start()
    await engine.pause()
    await engine.resume()
    engine.set_speed(2.0)
    await engine.seek_to_sequence(1000)
    await engine.stop()
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import suppress
from types import TracebackType

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading import ReplayEventLoader
from asyncviz.replay.runtime.models.engine_cursor import EngineCursor
from asyncviz.replay.runtime.models.playback_state import (
    PlaybackSnapshot,
    PlaybackState,
)
from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.replay.runtime.replay_checkpoint_runtime import CheckpointRuntime
from asyncviz.replay.runtime.replay_clock import ReplayClock
from asyncviz.replay.runtime.replay_configuration import ReplayEngineConfig
from asyncviz.replay.runtime.replay_cursor_runtime import CursorRuntime
from asyncviz.replay.runtime.replay_diagnostics import (
    ReplayEngineDiagnostics,
    build_engine_diagnostics,
)
from asyncviz.replay.runtime.replay_dispatch import ReplayDispatch
from asyncviz.replay.runtime.replay_event_router import ReplayEventRouter
from asyncviz.replay.runtime.replay_observability import get_engine_metrics
from asyncviz.replay.runtime.replay_pause import PauseController
from asyncviz.replay.runtime.replay_playback import PlaybackController
from asyncviz.replay.runtime.replay_reducers import (
    ReducerRegistry,
)
from asyncviz.replay.runtime.replay_scheduler import ReplayScheduler
from asyncviz.replay.runtime.replay_seek_runtime import (
    ReplaySeekRuntime,
    SeekOutcome,
)
from asyncviz.replay.runtime.replay_snapshot_runtime import SnapshotRuntime
from asyncviz.replay.runtime.replay_speed import SpeedController
from asyncviz.replay.runtime.replay_state_store import ReplayStateStore
from asyncviz.replay.runtime.replay_tracing import record_engine_trace
from asyncviz.replay.runtime.replay_websocket_bridge import (
    NullSink,
    ReplayWebsocketBridge,
    ReplayWebsocketSink,
)


class ReplayRuntimeEngine:
    """Top-level façade for replay playback."""

    __slots__ = (
        "_bridge",
        "_checkpoints",
        "_clock",
        "_config",
        "_controller",
        "_cursor",
        "_dispatch",
        "_loader",
        "_pause",
        "_reducers",
        "_router",
        "_scheduler",
        "_seek_runtime",
        "_snapshot_runtime",
        "_speed",
        "_state_store",
    )

    def __init__(
        self,
        *,
        loader: ReplayEventLoader,
        config: ReplayEngineConfig | None = None,
        reducers: ReducerRegistry | None = None,
        sink: ReplayWebsocketSink | None = None,
    ) -> None:
        cfg = config or ReplayEngineConfig()
        self._config = cfg
        self._loader = loader
        self._clock = ReplayClock(initial_speed=cfg.initial_speed)
        self._speed = SpeedController(self._clock)
        self._pause = PauseController(self._clock)
        self._scheduler = ReplayScheduler(
            self._clock,
            mode=cfg.playback_mode,
            catch_up_threshold_seconds=cfg.catch_up_threshold_seconds,
        )
        self._reducers = reducers or ReducerRegistry()
        self._state_store = ReplayStateStore()
        self._router = ReplayEventRouter()
        active_sink = sink if cfg.websocket_enabled else NullSink()
        if active_sink is None:
            active_sink = NullSink()
        self._bridge = ReplayWebsocketBridge(active_sink)
        self._checkpoints = CheckpointRuntime()
        self._snapshot_runtime = SnapshotRuntime(
            loader.snapshot_index,
            self._state_store,
        )
        self._cursor = CursorRuntime()
        self._dispatch = ReplayDispatch(
            reducers=self._reducers,
            state_store=self._state_store,
            router=self._router,
            bridge=self._bridge,
            checkpoints=self._checkpoints,
            checkpoint_interval=cfg.checkpoint_interval_frames,
        )
        self._seek_runtime = ReplaySeekRuntime(
            loader=loader,
            reducers=self._reducers,
            state_store=self._state_store,
            cursor=self._cursor,
            clock=self._clock,
            checkpoints=self._checkpoints,
        )
        self._controller = PlaybackController(
            scheduler=self._scheduler,
            clock=self._clock,
            pause=self._pause,
            dispatch=self._dispatch,
            cursor=self._cursor,
            strict_mode=cfg.enforce_strict_ordering,
        )

    # ── public accessors ──────────────────────────────────────────

    @property
    def config(self) -> ReplayEngineConfig:
        return self._config

    @property
    def loader(self) -> ReplayEventLoader:
        return self._loader

    @property
    def clock(self) -> ReplayClock:
        return self._clock

    @property
    def reducers(self) -> ReducerRegistry:
        return self._reducers

    @property
    def state(self) -> VirtualRuntimeState:
        return self._state_store.state

    @property
    def cursor(self) -> EngineCursor:
        return self._cursor.cursor

    @property
    def router(self) -> ReplayEventRouter:
        return self._router

    @property
    def bridge(self) -> ReplayWebsocketBridge:
        return self._bridge

    @property
    def checkpoints(self) -> CheckpointRuntime:
        return self._checkpoints

    @property
    def state_store(self) -> ReplayStateStore:
        return self._state_store

    @property
    def playback_state(self) -> PlaybackState:
        return self._controller.playback_state

    # ── playback control ──────────────────────────────────────────

    async def play(self, *, frames: Iterator[ReplayFrame] | None = None) -> None:
        """Start the playback loop. By default streams every frame
        from the loader; tests can supply a custom iterator."""
        if frames is None:
            frames = self._loader.iter_frames()
        await self._controller.play(frames)

    async def stop(self) -> None:
        await self._controller.stop()

    async def pause(self) -> bool:
        flipped = self._pause.pause()
        if flipped:
            get_engine_metrics().record_pause()
            record_engine_trace("pause")
        return flipped

    async def resume(self) -> bool:
        flipped = self._pause.resume()
        if flipped:
            get_engine_metrics().record_resume()
            record_engine_trace("resume")
        return flipped

    def set_speed(self, speed: float) -> float:
        result = self._speed.set(speed)
        get_engine_metrics().record_speed_change()
        record_engine_trace("speed-changed", f"speed={result}")
        return result

    def step(self) -> None:
        self._controller.step()

    async def wait_until_done(self) -> None:
        await self._controller.wait_until_done()

    # ── seek ──────────────────────────────────────────────────────

    def seek_to_sequence(self, target_sequence: int) -> SeekOutcome:
        record_engine_trace("seek-started", f"target_seq={target_sequence}")
        outcome = self._seek_runtime.seek_to_sequence(target_sequence)
        get_engine_metrics().record_seek()
        if outcome.used_snapshot:
            get_engine_metrics().record_snapshot_restored()
            record_engine_trace(
                "snapshot-restored",
                f"target_seq={target_sequence}",
            )
        record_engine_trace(
            "seek-completed",
            f"target_seq={target_sequence} checkpoint={outcome.used_checkpoint}",
        )
        return outcome

    def restore_snapshot_at(self, sequence: int) -> VirtualRuntimeState:
        result = self._snapshot_runtime.restore_for_sequence(sequence)
        get_engine_metrics().record_snapshot_restored()
        record_engine_trace("snapshot-restored", f"seq={sequence}")
        return result.state

    # ── diagnostics ───────────────────────────────────────────────

    def snapshot(self) -> PlaybackSnapshot:
        return self._controller.snapshot()

    def diagnostics(self) -> ReplayEngineDiagnostics:
        return build_engine_diagnostics(self.snapshot())

    # ── async context manager ─────────────────────────────────────

    async def __aenter__(self) -> ReplayRuntimeEngine:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        with suppress(Exception):
            await self.stop()
