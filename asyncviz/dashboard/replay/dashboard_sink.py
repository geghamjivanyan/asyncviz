"""Dashboard-facing :class:`ReplayWebsocketSink` implementation.

Bridges the replay :class:`ReplayRuntimeEngine` to the dashboard's
existing websocket fan-out. The engine emits :class:`ReplayFrame`s;
this sink turns each into a canonical :class:`Envelope`
(``runtime_event`` for live events, ``runtime_snapshot`` for snapshot
frames) and broadcasts it through :class:`ConnectionManager`.

The frontend's existing reducer + selectors handle the envelopes
identically to a live runtime. From the SPA's perspective the
realtime stream simply happens to be sourced from a recording.

Threading notes
---------------
The replay engine runs on the CLI process's main asyncio loop. The
dashboard runs on uvicorn's daemon-thread loop. The sink is invoked
from the engine's loop; we hop over to the dashboard's loop with
:func:`asyncio.run_coroutine_threadsafe` so the broadcast actually
runs on the loop that owns the websocket sockets. The hop completes
synchronously from the engine's perspective (via ``await
asyncio.wrap_future``), so back-pressure naturally propagates: if
the dashboard loop is busy, the engine slows down to match.
"""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from asyncviz.dashboard.websocket.manager import ConnectionManager
from asyncviz.dashboard.websocket.protocol import (
    Envelope,
    runtime_event,
    runtime_snapshot,
)
from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.runtime.models.runtime_state import VirtualRuntimeState
from asyncviz.utils.logging import get_logger

logger = get_logger("dashboard.replay.sink")


class DashboardReplaySink:
    """Convert :class:`ReplayFrame`s into dashboard envelopes + broadcast.

    Construct one per replay session. The sink holds a weak link to
    the :class:`ConnectionManager` (whose lifetime tracks the
    dashboard's lifespan) and the dashboard's event loop reference
    (where the broadcast must actually run).

    Implements the :class:`ReplayWebsocketSink` protocol —
    ``push_frame`` / ``push_state`` — but does not import the
    protocol directly to keep this module independent of the replay
    package's type plumbing (the duck-typed contract is enough).
    """

    __slots__ = (
        "_dashboard_loop",
        "_frames_pushed",
        "_frames_skipped",
        "_manager",
        "_states_pushed",
    )

    def __init__(
        self,
        *,
        manager: ConnectionManager,
        dashboard_loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._manager = manager
        self._dashboard_loop = dashboard_loop
        self._frames_pushed = 0
        self._frames_skipped = 0
        self._states_pushed = 0

    # ── public counters (test hooks) ─────────────────────────────────
    @property
    def frames_pushed(self) -> int:
        return self._frames_pushed

    @property
    def frames_skipped(self) -> int:
        return self._frames_skipped

    @property
    def states_pushed(self) -> int:
        return self._states_pushed

    # ── ReplayWebsocketSink protocol ─────────────────────────────────
    async def push_frame(self, frame: ReplayFrame) -> None:
        envelope = self._envelope_for(frame)
        if envelope is None:
            # marker / snapshot_delta / unknown — not part of the
            # live wire taxonomy. Tally for diagnostics but don't
            # surface to the frontend (it would just reject as
            # unknown type via parseEnvelope).
            self._frames_skipped += 1
            return
        await self._broadcast(envelope)
        self._frames_pushed += 1

    async def push_state(self, state: VirtualRuntimeState) -> None:
        # The state-store snapshot is debug-grade introspection; the
        # frontend already keeps its own normalised projections via
        # the per-envelope reducers. We don't currently flush a
        # synthetic ``runtime_snapshot`` here because the bundle's
        # own snapshot frames are forwarded by ``push_frame`` above
        # — those carry the canonical wire shape. Tallying is enough
        # for diagnostics.
        self._states_pushed += 1

    # ── conversion ───────────────────────────────────────────────────
    def _envelope_for(self, frame: ReplayFrame) -> Envelope | None:
        """Map one :class:`ReplayFrame` to a dashboard envelope.

        Only frame types the frontend understands today are emitted:

          * ``runtime_event`` — verbatim payload + recorded sequence.
          * ``snapshot_begin`` — converted to a ``runtime_snapshot``
            envelope so the frontend's reducer rehydrates task /
            timeline / metric / warning projections from the
            recording's own captured baseline.

        Returns ``None`` for frame types the wire doesn't consume
        (markers, snapshot_end, snapshot_delta). The caller counts
        these as "skipped" rather than dropping silently.
        """
        ftype = frame.frame_type
        if ftype == "runtime_event":
            # The payload is the wire-shape :class:`RuntimeEvent`
            # serialization the recorder captured. The frontend's
            # central reducer routes by ``payload.event_type`` —
            # works identically whether the source is live or
            # recorded.
            return runtime_event(dict(frame.payload), sequence=frame.sequence)
        if ftype == "snapshot_begin":
            return self._snapshot_envelope_from(frame)
        return None

    @staticmethod
    def _snapshot_envelope_from(frame: ReplayFrame) -> Envelope | None:
        """Construct a ``runtime_snapshot`` envelope from a snapshot frame.

        The recorder captured the same :class:`RuntimeSnapshotPayload`
        the live websocket emits on first-connect; we forward it
        unchanged so the frontend's :func:`reduceRuntimeSnapshotEnvelope`
        rehydrates its projections off the recording's own baseline.
        Returns ``None`` if the payload is missing required fields —
        the caller treats that as a skipped frame.
        """
        payload = frame.payload
        if not isinstance(payload, dict):
            return None
        # Required by the frontend reducer + by the client's
        # sequence cursor — without ``last_sequence`` the replay
        # cursor would never advance past the snapshot frame.
        if "last_sequence" not in payload:
            return None
        try:
            return runtime_snapshot(
                last_sequence=int(payload.get("last_sequence", 0)),
                tasks=list(payload.get("tasks", []) or []),
                metrics=dict(payload.get("metrics", {}) or {}),
                clock=payload.get("clock"),
                queue=payload.get("queue"),
                state=payload.get("state"),
            )
        except Exception:
            logger.exception("replay snapshot frame failed envelope construction")
            return None

    # ── cross-loop broadcast ─────────────────────────────────────────
    async def _broadcast(self, envelope: Envelope) -> None:
        """Run :meth:`ConnectionManager.broadcast` on the dashboard loop.

        The replay engine's frame dispatch runs on whichever loop the
        CLI launcher uses. The connection manager + its websocket
        clients live on the dashboard's daemon-thread loop. Crossing
        thread boundaries on the broadcast side preserves the
        websocket lib's "single-loop ownership" invariant.
        """
        coro = self._manager.broadcast(envelope)
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop is self._dashboard_loop:
            with suppress(Exception):
                await coro
            return

        # Schedule on the dashboard loop. ``run_coroutine_threadsafe``
        # returns a concurrent.futures.Future; bridge it back via
        # ``asyncio.wrap_future`` so the engine awaits delivery and
        # back-pressure propagates correctly.
        future = asyncio.run_coroutine_threadsafe(coro, self._dashboard_loop)
        try:
            await asyncio.wrap_future(future)
        except Exception:
            logger.exception("replay broadcast failed; dropping frame")

    # ── diagnostics ──────────────────────────────────────────────────
    def diagnostics(self) -> dict[str, Any]:
        return {
            "frames_pushed": self._frames_pushed,
            "frames_skipped": self._frames_skipped,
            "states_pushed": self._states_pushed,
        }
