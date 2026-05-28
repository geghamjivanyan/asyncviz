"""Replay reproducibility scenario.

Emits one ``replay-frame`` signal per synthetic frame; the runner
checks that two runs with the same seed produce identical signal
fingerprints via :func:`fingerprint_signals`.
"""

from __future__ import annotations

from tests.integration.harness.scenario_context import IntegrationContext
from tests.integration.synthetic import generate_replay_stream


async def run_replay_determinism(context: IntegrationContext) -> None:
    for frame in generate_replay_stream(
        frames=context.config.replay_frames,
        seed=context.rng.seed,
    ):
        context.record(
            "replay-frame",
            f"{frame.sequence}:{frame.payload_kind}",
            value=frame.time_seconds,
        )
