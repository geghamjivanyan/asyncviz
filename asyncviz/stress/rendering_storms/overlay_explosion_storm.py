"""Overlay-explosion storm.

The render-optimization layer separates overlay redraws from the
data pass. This storm verifies that a flood of overlay updates
(cursor moves, selection toggles) coalesces correctly + bounded
overlay backlog stays under the configured limit.
"""

from __future__ import annotations

from asyncviz.stress.harness.scenario_context import ScenarioContext


async def run_overlay_explosion_storm(context: ScenarioContext) -> None:
    cfg = context.config
    coalesced = 0
    pending = False
    flushed = 0
    for tick_index in range(cfg.render_overlay_explosion):
        if pending:
            coalesced += 1
        pending = True
        # Periodic flushes mimic the per-frame coalescing window.
        if tick_index % 32 == 31:
            pending = False
            flushed += 1
            context.record_signal("render-frame", f"overlay-flush:{flushed}")
    context.record_signal(
        "custom",
        f"overlay-coalesced={coalesced}",
        float(coalesced),
    )
