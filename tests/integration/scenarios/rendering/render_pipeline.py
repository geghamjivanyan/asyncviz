"""Render-pipeline integration scenario."""

from __future__ import annotations

from tests.integration.harness.scenario_context import IntegrationContext
from tests.integration.synthetic import generate_render_stream


async def run_render_pipeline(context: IntegrationContext) -> None:
    cfg = context.config
    drops = 0
    frames_drawn = 0
    for tick in generate_render_stream(frames=cfg.render_frames, seed=context.rng.seed):
        if tick.drop:
            drops += 1
            context.record("render-drop", f"frame={tick.frame_index}")
        else:
            frames_drawn += 1
            context.record("render-frame", f"frame={tick.frame_index}")
    context.record(
        "custom",
        f"render-drops={drops} frames-drawn={frames_drawn}",
        value=float(drops),
    )
