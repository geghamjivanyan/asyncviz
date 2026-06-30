"""Cross-chunk streaming iterator.

The :class:`ReplayStream` is the loader's central read-side
primitive: hand it a list of chunk loaders and a starting cursor,
and it yields decoded :class:`ReplayFrame` objects in canonical
sequence order, advancing the cursor as it goes.

Filtering / windowing live as composable wrappers on top of this
stream so the loader doesn't need to know about them — the stream
itself stays small and focused on chunk-walk ordering.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.loading.replay_chunk_loader import ReplayChunkLoader
from asyncviz.replay.loading.replay_cursor import ReplayCursor
from asyncviz.replay.loading.replay_filtering import FrameFilter
from asyncviz.replay.loading.replay_observability import get_loader_metrics
from asyncviz.replay.loading.replay_tracing import record_replay_trace
from asyncviz.replay.loading.replay_windowing import ReplayWindow


@dataclass(slots=True)
class StreamProgress:
    """Mutable progress counters surfaced by the stream."""

    cursor: ReplayCursor = field(default_factory=ReplayCursor.at_start)
    filtered_drops: int = 0
    window_drops: int = 0
    advanced_by: int = 0


class ReplayStream:
    """Iterates frames across an ordered sequence of chunk loaders."""

    __slots__ = ("_chunks", "_filter", "_progress", "_window")

    def __init__(
        self,
        chunks: Iterable[ReplayChunkLoader],
        *,
        window: ReplayWindow | None = None,
        frame_filter: FrameFilter | None = None,
        initial_cursor: ReplayCursor | None = None,
    ) -> None:
        self._chunks = list(chunks)
        self._window = window or ReplayWindow.unbounded()
        self._filter = frame_filter
        self._progress = StreamProgress(
            cursor=initial_cursor or ReplayCursor.at_start(),
        )

    @property
    def progress(self) -> StreamProgress:
        return self._progress

    @property
    def cursor(self) -> ReplayCursor:
        return self._progress.cursor

    def __iter__(self) -> Iterator[ReplayFrame]:
        for chunk_loader in self._chunks:
            for frame in chunk_loader.iter_frames():
                # Window — early-stop when above the upper bound.
                if self._window.above_window(frame):
                    record_replay_trace(
                        "window-drop",
                        f"seq={frame.sequence} above-window",
                    )
                    self._progress.window_drops += 1
                    get_loader_metrics().record_window_drop()
                    return
                if self._window.below_window(frame):
                    self._progress.window_drops += 1
                    get_loader_metrics().record_window_drop()
                    continue
                if self._filter is not None and not self._filter(frame):
                    self._progress.filtered_drops += 1
                    get_loader_metrics().record_filter_drop()
                    continue
                self._progress.cursor = self._progress.cursor.advance(
                    chunk_index=chunk_loader.chunk.index,
                    sequence=frame.sequence,
                    monotonic_ns=frame.monotonic_ns,
                )
                self._progress.advanced_by += 1
                get_loader_metrics().record_frame_loaded()
                yield frame
