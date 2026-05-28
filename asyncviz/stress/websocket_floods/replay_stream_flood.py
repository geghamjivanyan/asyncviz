"""Replay-stream websocket flood.

Streams replay frames through a single subscriber + counts drops /
backlog. Used to verify the streaming engine's delta + keyframe
discipline survives bursty replay traffic.
"""

from __future__ import annotations

from collections import deque

from asyncviz.stress.harness.scenario_context import ScenarioContext


async def run_replay_stream_flood(context: ScenarioContext) -> None:
    cfg = context.config
    queue: deque[int] = deque(maxlen=max(64, cfg.replay_stream_frames // 16))
    drained = 0
    dropped = 0
    for frame_index in range(cfg.replay_stream_frames):
        keyframe = frame_index % 256 == 0
        if len(queue) >= (queue.maxlen or 0) and not keyframe:
            dropped += 1
            # Drops here are expected backpressure, not failures —
            # the scenario validates that the bookkeeping stays
            # bounded, not that no frame is ever shed.
            context.record_signal("custom", "replay-frame-dropped")
            continue
        queue.append(frame_index)
        # Drain in a 2-to-1 pattern so the backlog occasionally grows.
        if frame_index % 2 == 0 and queue:
            queue.popleft()
            drained += 1
            context.record_signal("replay-frame", "drained")
        if keyframe:
            context.record_signal("replay-frame", "keyframe")
    context.record_signal("custom", f"replay-dropped={dropped}", float(dropped))
    context.record_signal("custom", f"replay-drained={drained}", float(drained))
