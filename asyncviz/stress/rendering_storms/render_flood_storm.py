"""Render-flood storm.

Drives a synthetic render pipeline with ``render_flood_frames`` frame
ticks and ``render_flood_regions`` invalidations per second. The
scenario maintains a synthetic frame-budget governor; bursts that
exceed the per-frame budget are recorded as drops + an overload
signal.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from asyncviz.stress.harness.scenario_context import ScenarioContext


@dataclass(slots=True)
class _SyntheticFrameBudget:
    soft_ms: float
    hard_ms: float
    over_streak: int = 0
    degraded: bool = False


async def run_render_flood_storm(context: ScenarioContext) -> None:
    cfg = context.config
    budget = _SyntheticFrameBudget(
        soft_ms=cfg.replay_frame_budget_ms / 2,
        hard_ms=cfg.replay_frame_budget_ms,
    )
    regions: deque[int] = deque(maxlen=cfg.render_flood_regions)
    rng = context.rng
    for frame_index in range(cfg.render_flood_frames):
        # Synthetic per-frame cost: a base cost plus a noise term.
        cost_ms = max(0.0, rng.jitter(budget.soft_ms * 0.6, 0.5))
        invalidations = rng.integer(1, 32)
        for _ in range(invalidations):
            regions.append(frame_index)
        if cost_ms > budget.hard_ms:
            budget.over_streak += 1
            context.record_signal("failure", f"render-frame-overrun:{cost_ms:.2f}ms")
        else:
            context.record_signal("render-frame", f"frame={frame_index} cost={cost_ms:.2f}")
        if budget.over_streak >= 3 and not budget.degraded:
            budget.degraded = True
            context.record_signal("overload", "render-budget-degraded")
        elif budget.over_streak == 0 and budget.degraded:
            budget.degraded = False
            context.record_signal("custom", "render-budget-restored")
        if cost_ms <= budget.hard_ms:
            budget.over_streak = 0
    context.record_signal(
        "custom",
        f"render-frames={cfg.render_flood_frames}",
        float(cfg.render_flood_frames),
    )
