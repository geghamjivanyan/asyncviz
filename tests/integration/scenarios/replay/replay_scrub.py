"""Rapid replay-scrub storm.

Drives ``replay_frames`` rapid seek operations + emits a custom
checksum signal so the runner can confirm two runs produce the
exact same scrub pattern.
"""

from __future__ import annotations

from tests.integration.harness.scenario_context import IntegrationContext


async def run_replay_scrub_storm(context: IntegrationContext) -> None:
    cfg = context.config
    checksum = 0
    for hop_index in range(cfg.replay_frames):
        target = context.rng.integer(0, cfg.replay_frames - 1)
        checksum = (checksum * 31 + target) & 0xFFFFFFFF
        context.record(
            "replay-frame",
            f"scrub:{hop_index}->{target}",
            value=float(target),
        )
    context.record("custom", f"scrub-checksum={checksum}", value=float(checksum))
