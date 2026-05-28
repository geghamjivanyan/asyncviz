"""Periodic emitter for the ``replay_status`` envelope.

Sits between :class:`ReplayRuntimeEngine` and the dashboard's
:class:`ConnectionManager`. Snapshots the engine on a small cadence
(plus once at startup and once on shutdown) and broadcasts the
result so the SPA's replay timeline can hydrate the session window,
playback state, speed, and bundle metadata.

Why a separate emitter (rather than piggybacking on the existing
``DashboardReplaySink``):

* The sink translates per-frame events 1:1. The replay-status
  payload is whole-session metadata — it doesn't move with every
  frame; coupling it to the per-frame path would either flood the
  socket or rate-limit downstream consumers.
* The first ``replay_status`` must land BEFORE the first
  ``runtime_event`` envelope, so the frontend has a populated
  session window when the events start arriving. Owning a separate
  loop makes that ordering explicit.
* Late-joining websocket clients (a browser refresh mid-replay)
  need to receive the current status promptly. A cadence-driven
  broadcaster handles that without re-plumbing the engine.

The broadcaster:

  * emits once on ``start`` (carrying the bundle's static metadata),
  * emits at ``interval_seconds`` cadence (default 0.5 s) while
    playback is active,
  * emits a final ``stopped`` snapshot during ``stop``,
  * runs on the dashboard's loop via ``run_coroutine_threadsafe``
    so the broadcast stays on the loop that owns the websocket
    clients.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from asyncviz.dashboard.websocket.protocol import replay_status
from asyncviz.utils.logging import get_logger

if TYPE_CHECKING:
    from asyncviz.dashboard.websocket.manager import ConnectionManager
    from asyncviz.replay.runtime import ReplayRuntimeEngine

logger = get_logger("dashboard.replay.broadcaster")


@dataclass(frozen=True, slots=True)
class ReplayRecordingMetadata:
    """Static metadata about the loaded recording.

    Filled in by the launcher when the bundle opens — the broadcaster
    never re-reads it. Kept frozen so the broadcaster can re-emit it
    repeatedly without copy churn.
    """

    bundle_id: str
    runtime_id: str | None
    event_count: int
    chunk_count: int
    snapshot_count: int
    last_sequence: int
    finalized: bool
    source_label: str
    """Human-readable source description — e.g. the bundle path."""

    def to_payload(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "runtime_id": self.runtime_id,
            "event_count": self.event_count,
            "chunk_count": self.chunk_count,
            "snapshot_count": self.snapshot_count,
            "last_sequence": self.last_sequence,
            "finalized": self.finalized,
            "source_label": self.source_label,
        }


class ReplayStatusBroadcaster:
    """Emit ``replay_status`` envelopes on a regular cadence.

    Construct one per replay session. The launcher calls
    :meth:`start` after the engine is set up, and :meth:`stop` in its
    finally block. ``start`` synchronously emits the initial
    "loaded" envelope so the SPA hydrates immediately; the
    background task takes over for subsequent updates.
    """

    __slots__ = (
        "_dashboard_loop",
        "_engine",
        "_interval_seconds",
        "_last_payload_signature",
        "_manager",
        "_metadata",
        "_started",
        "_stop_event",
        "_task",
    )

    def __init__(
        self,
        *,
        engine: ReplayRuntimeEngine,
        metadata: ReplayRecordingMetadata,
        manager: ConnectionManager,
        dashboard_loop: asyncio.AbstractEventLoop,
        interval_seconds: float = 0.5,
    ) -> None:
        self._engine = engine
        self._metadata = metadata
        self._manager = manager
        self._dashboard_loop = dashboard_loop
        self._interval_seconds = interval_seconds
        self._stop_event: asyncio.Event | None = None
        self._task: asyncio.Task[None] | None = None
        self._started = False
        self._last_payload_signature: tuple | None = None

    # ── lifecycle ────────────────────────────────────────────────────
    async def start(self) -> None:
        """Emit the initial status + spin up the cadence task.

        Idempotent — a second call before :meth:`stop` is a no-op.
        """
        if self._started:
            return
        self._started = True
        self._stop_event = asyncio.Event()
        # Initial emission BEFORE the engine begins dispatching frames.
        # The frontend's bridge needs the window populated by the time
        # the first runtime_event lands so its store transitions out
        # of "no recording loaded" cleanly.
        await self._broadcast_current()
        self._task = asyncio.create_task(self._run(), name="asyncviz-replay-status")

    async def stop(self) -> None:
        """Emit one final ``stopped`` status + tear down the task."""
        if not self._started:
            return
        self._started = False
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            with suppress(BaseException):
                await self._task
            self._task = None
        # Final emission — the SPA leaves the "stopped" state visible
        # after playback completes so the operator can still inspect
        # the timeline.
        with suppress(BaseException):
            await self._broadcast_current()

    # ── cadence loop ─────────────────────────────────────────────────
    async def _run(self) -> None:
        assert self._stop_event is not None
        try:
            while not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._interval_seconds,
                    )
                    return
                except TimeoutError:
                    pass
                await self._broadcast_current()
        except asyncio.CancelledError:
            raise

    # ── one-shot emission ────────────────────────────────────────────
    async def _broadcast_current(self) -> None:
        payload = self._build_payload()
        # Suppress redundant emissions — the cadence loop fires
        # regardless of whether anything moved; the dedup keeps
        # the wire quiet between actual changes.
        signature = self._signature_of(payload)
        if signature == self._last_payload_signature:
            return
        self._last_payload_signature = signature

        envelope = replay_status(payload)
        # Cross-thread / cross-loop hop: the engine runs on the CLI
        # main loop, the connection manager lives on the dashboard
        # loop. Hop over so the broadcast happens on the loop that
        # owns the websocket clients.
        coro = self._manager.broadcast(envelope)
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if current_loop is self._dashboard_loop:
            with suppress(Exception):
                await coro
            return
        future = asyncio.run_coroutine_threadsafe(coro, self._dashboard_loop)
        try:
            await asyncio.wrap_future(future)
        except Exception:
            logger.debug("replay_status broadcast failed", exc_info=True)

    # ── payload construction ─────────────────────────────────────────
    def _build_payload(self) -> dict[str, Any]:
        """Snapshot the engine + metadata into the wire-shape payload.

        Wire contract (consumed by :class:`WebSocketReplayEngineBridge`
        on the frontend):

        ``{recording: ReplayRecordingMetadata, playback: {state, speed,
        last_sequence, last_monotonic_ns, frames_dispatched, paused,
        queue_depth, error_detail}, window: {min_sequence, max_sequence,
        min_monotonic_ns, max_monotonic_ns}}``
        """
        snapshot = self._engine.snapshot()
        # Bundle metadata is static — read once at construction.
        window = self._derive_window(snapshot)
        return {
            "recording": self._metadata.to_payload(),
            "playback": {
                "state": snapshot.state.value,
                "speed": snapshot.speed,
                "last_sequence": snapshot.last_sequence,
                "last_monotonic_ns": snapshot.last_monotonic_ns,
                "frames_dispatched": snapshot.frames_dispatched,
                "queue_depth": snapshot.queue_depth,
                "paused": snapshot.paused,
                "error_detail": snapshot.error_detail or "",
            },
            "window": window,
        }

    def _derive_window(self, snapshot: Any) -> dict[str, int]:
        """Compute the session window from bundle metadata + cursor.

        ``max_sequence`` is the recording's terminal sequence (known
        from the bundle); ``min_sequence`` is its first observed
        sequence. ``monotonic_ns`` bounds default to 0 until the first
        snapshot/frame arrives — the SPA's geometry code clamps
        against that gracefully.
        """
        return {
            "min_sequence": 1,
            "max_sequence": int(self._metadata.last_sequence),
            "min_monotonic_ns": 0,
            "max_monotonic_ns": int(snapshot.last_monotonic_ns or 0),
        }

    @staticmethod
    def _signature_of(payload: dict[str, Any]) -> tuple:
        """Dedup signature — coarse but cheap.

        Two emissions whose state, last_sequence, frames_dispatched,
        speed, paused, and window are identical are treated as
        duplicate.
        """
        playback = payload.get("playback", {})
        window = payload.get("window", {})
        return (
            playback.get("state"),
            playback.get("last_sequence"),
            playback.get("frames_dispatched"),
            playback.get("speed"),
            playback.get("paused"),
            playback.get("error_detail"),
            window.get("min_sequence"),
            window.get("max_sequence"),
        )
