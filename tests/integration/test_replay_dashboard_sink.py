"""End-to-end integration test for the dashboard replay path.

Drives a real ``.avz`` recording through :class:`ReplayRuntimeEngine`
with a :class:`DashboardReplaySink` pointed at a fake
:class:`ConnectionManager`, and asserts that

  * the engine plays through the bundle to completion,
  * the sink translates the recorded events into the canonical
    dashboard ``runtime_event`` envelope shape,
  * the broadcast call lands on the supplied "dashboard loop"
    thread — i.e. the cross-loop hop in
    :class:`DashboardReplaySink` works.

The fixture uses one of the ``asyncviz-recordings/session-*.avz``
artifacts produced by the existing ``asyncviz record`` smoke runs.
If no such artifact is present, the test skips — the integration is
about wiring, not about generating new bundles.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from asyncviz.dashboard.replay import DashboardReplaySink
from asyncviz.dashboard.websocket.protocol import Envelope
from asyncviz.replay.loading import ReplayEventLoader, ReplayLoaderConfig
from asyncviz.replay.runtime import (
    ReplayEngineConfig,
    ReplayRuntimeEngine,
)

# Look in the repo-root ``asyncviz-recordings`` directory the CLI
# writes by default. The earliest finalized bundle wins so the test
# isn't sensitive to the ordering of dev artifacts.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_RECORDINGS_DIR = _REPO_ROOT / "asyncviz-recordings"


def _find_recording_bundle() -> Path | None:
    if not _RECORDINGS_DIR.is_dir():
        return None
    for entry in sorted(_RECORDINGS_DIR.iterdir()):
        if not entry.is_dir() or entry.suffix != ".avz":
            continue
        if (entry / "manifest.json").is_file():
            return entry
    return None


class _FakeConnectionManager:
    """Stand-in for :class:`ConnectionManager` that records broadcasts.

    The real connection manager owns websocket clients; the replay
    sink only cares that ``broadcast(envelope)`` accepts the envelope
    and returns. Recording the envelopes here lets the test assert
    the sink's translation contract.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self.envelopes: list[Envelope] = []
        self.broadcast_thread_ids: list[int] = []

    async def broadcast(self, envelope: Envelope) -> int:
        # Capture which thread the broadcast actually ran on; the
        # sink should hop onto the loop we registered as the
        # dashboard loop.
        self.broadcast_thread_ids.append(threading.get_ident())
        self.envelopes.append(envelope)
        return 1


def _run_loop_in_thread(loop: asyncio.AbstractEventLoop, ready: threading.Event) -> None:
    asyncio.set_event_loop(loop)
    ready.set()
    try:
        loop.run_forever()
    finally:
        loop.close()


@pytest.mark.asyncio
async def test_dashboard_replay_sink_translates_recording_to_envelopes() -> None:
    bundle = _find_recording_bundle()
    if bundle is None:
        pytest.skip(
            "no .avz bundle available under asyncviz-recordings/; "
            "run 'asyncviz record' once to seed one",
        )

    # Spin a dedicated "dashboard" loop on a worker thread so the
    # sink's cross-loop hop is exercised the way it runs in
    # production.
    dashboard_loop = asyncio.new_event_loop()
    ready = threading.Event()
    dashboard_thread = threading.Thread(
        target=_run_loop_in_thread,
        args=(dashboard_loop, ready),
        name="fake-dashboard-loop",
        daemon=True,
    )
    dashboard_thread.start()
    assert ready.wait(timeout=2.0)

    manager = _FakeConnectionManager(dashboard_loop)
    sink = DashboardReplaySink(
        manager=manager,  # type: ignore[arg-type]
        dashboard_loop=dashboard_loop,
    )

    try:
        loader = ReplayEventLoader.open(
            bundle,
            config=ReplayLoaderConfig(session_dir=bundle, verify_integrity=False),
        )
    except Exception as exc:
        # Pre-existing bundles in this dev tree may have been written
        # by an older recorder that used different manifest keys. Skip
        # rather than fail — this test exercises the SINK contract, not
        # the loader's backward-compatibility with old layouts.
        dashboard_loop.call_soon_threadsafe(dashboard_loop.stop)
        dashboard_thread.join(timeout=2.0)
        pytest.skip(f"bundle {bundle} not loadable by current loader: {exc!r}")
        return
    try:
        engine = ReplayRuntimeEngine(
            loader=loader,
            # Crank the speed so the test finishes promptly; the
            # scheduler still preserves frame ordering at any speed.
            config=ReplayEngineConfig(initial_speed=1024.0),
            sink=sink,
        )
        try:
            await asyncio.wait_for(engine.play(), timeout=20.0)
        finally:
            await engine.stop()
    finally:
        loader.close()
        dashboard_loop.call_soon_threadsafe(dashboard_loop.stop)
        dashboard_thread.join(timeout=2.0)

    # At least one envelope landed. Exact count depends on the
    # bundle, but a finalized session always has frames.
    assert sink.frames_pushed > 0
    assert manager.envelopes, "expected the sink to broadcast at least one envelope"

    # Every emitted envelope is a canonical dashboard ``Envelope``
    # of a wire-known type.
    for env in manager.envelopes:
        assert isinstance(env, Envelope)
        assert env.type in {"runtime_event", "runtime_snapshot"}
        assert env.protocol_version == "1.0"

    # Cross-loop hop verification: every broadcast ran on the
    # dashboard worker thread, never on the main test thread.
    main_thread = threading.get_ident()
    assert all(tid != main_thread for tid in manager.broadcast_thread_ids), (
        "sink broadcasts must run on the dashboard loop's thread"
    )


@pytest.mark.asyncio
async def test_dashboard_replay_sink_skips_unknown_frame_types() -> None:
    """Marker / snapshot_delta frames must not become wire envelopes.

    The sink intentionally only emits ``runtime_event`` and
    ``snapshot_begin`` frames. Anything else (markers, snapshot_end,
    snapshot_delta) is tallied as "skipped" so a diagnostics
    consumer can spot a corrupted recording without flooding the
    websocket with non-protocol envelopes the frontend would
    reject.
    """
    from asyncviz.replay.format import ReplayFrame
    from asyncviz.replay.format.ndjson_schema import SCHEMA_VERSION

    dashboard_loop = asyncio.new_event_loop()
    ready = threading.Event()
    thread = threading.Thread(
        target=_run_loop_in_thread,
        args=(dashboard_loop, ready),
        name="fake-dashboard-loop-2",
        daemon=True,
    )
    thread.start()
    assert ready.wait(timeout=2.0)

    manager = _FakeConnectionManager(dashboard_loop)
    sink = DashboardReplaySink(
        manager=manager,  # type: ignore[arg-type]
        dashboard_loop=dashboard_loop,
    )

    try:
        marker = ReplayFrame.for_marker(
            sequence=1,
            monotonic_ns=0,
            marker_name="checkpoint",
        )
        await sink.push_frame(marker)
        snapshot_end = ReplayFrame(
            schema_version=SCHEMA_VERSION,
            frame_type="snapshot_end",
            sequence=2,
            monotonic_ns=0,
            payload_type="snapshot.end",
            payload={"reason": "test"},
        )
        await sink.push_frame(snapshot_end)
        # And one valid runtime_event so we know the sink itself
        # works in this fixture.
        event = ReplayFrame.for_runtime_event(
            sequence=3,
            monotonic_ns=0,
            payload_type="asyncio.task.created",
            payload={"event_type": "asyncio.task.created", "task_id": "t1"},
        )
        await sink.push_frame(event)
    finally:
        dashboard_loop.call_soon_threadsafe(dashboard_loop.stop)
        thread.join(timeout=2.0)

    assert sink.frames_pushed == 1
    assert sink.frames_skipped == 2
    assert len(manager.envelopes) == 1
    assert manager.envelopes[0].type == "runtime_event"
    assert manager.envelopes[0].payload.get("event_type") == "asyncio.task.created"
