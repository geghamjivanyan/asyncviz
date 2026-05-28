"""End-to-end task-lifecycle pipeline.

Drives a deterministic batch of synthetic task descriptors through:

1. instrumentation (we *simulate* — no real asyncio.Task), so the
   pipeline is timing-stable across machines,
2. a synthetic websocket fanout (emits ``operation`` per task),
3. a synthetic replay frame stream (emits ``replay-frame`` per
   delta + ``custom`` per keyframe),
4. a synthetic render tick stream (emits ``render-frame`` /
   ``render-drop``).

The scenario asserts nothing on its own — the runner aggregates
signals + the threshold validator decides pass/fail.
"""

from __future__ import annotations

import asyncio

from tests.integration.harness.scenario_context import IntegrationContext
from tests.integration.synthetic import (
    generate_render_stream,
    generate_replay_stream,
    generate_task_storm,
)


async def run_task_lifecycle_pipeline(context: IntegrationContext) -> None:
    cfg = context.config
    seed = context.rng.seed
    for descriptor in generate_task_storm(
        size=cfg.task_count,
        seed=seed,
        dependency_depth=4,
    ):
        context.record("operation", f"task:{descriptor.task_id}")
        await asyncio.sleep(0)
    for frame in generate_replay_stream(frames=cfg.replay_frames, seed=seed):
        context.record(
            "replay-frame",
            f"sequence={frame.sequence}:kind={frame.payload_kind}",
        )
    for tick in generate_render_stream(
        frames=cfg.render_frames,
        seed=seed,
        drop_probability=0.0,
    ):
        if tick.drop:
            context.record("render-drop", f"frame={tick.frame_index}")
        else:
            context.record("render-frame", f"frame={tick.frame_index}")
