from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
import pytest_asyncio

from asyncviz.replay.recording import (
    RecordingConfig,
    reset_recording_metrics,
)
from asyncviz.replay.recording.recording_tracing import (
    clear_recording_trace,
    set_recording_trace_enabled,
)
from asyncviz.runtime.events import EventBus


@pytest.fixture(autouse=True)
def _reset_recording_globals() -> Iterator[None]:
    reset_recording_metrics()
    clear_recording_trace()
    set_recording_trace_enabled(False)
    yield
    reset_recording_metrics()
    clear_recording_trace()
    set_recording_trace_enabled(False)


@pytest.fixture
def recording_root(tmp_path: Path) -> Path:
    root = tmp_path / "recordings"
    root.mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture
def basic_config(recording_root: Path) -> RecordingConfig:
    return RecordingConfig(
        root_dir=recording_root,
        buffer_capacity=256,
        flush_interval_seconds=0.05,
        max_chunk_bytes=0,
        max_chunk_events=0,
        snapshot_on_start=False,
        snapshot_on_stop=False,
    )


@pytest_asyncio.fixture
async def bus() -> AsyncIterator[EventBus]:
    bus = EventBus()
    await bus.start()
    try:
        yield bus
    finally:
        await bus.stop()
