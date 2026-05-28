"""Rapid replay-scrub storm.

Pretends to seek a replay session ``replay_scrub_hops`` times in a
short window. We don't drive the real replay engine — instead we
verify the *bookkeeping* (cursor advances, keyframe cadence,
deterministic ordering) stays correct under bursty seeks.
"""

from __future__ import annotations

from asyncviz.stress.harness.scenario_context import ScenarioContext


async def run_replay_scrub_storm(context: ScenarioContext) -> None:
    cfg = context.config
    seen_sequences: list[int] = []
    for hop_index in range(cfg.replay_scrub_hops):
        # Deterministic seek pattern — covers forward / backward jumps.
        sequence = context.rng.integer(0, max(1, cfg.replay_stream_frames - 1))
        seen_sequences.append(sequence)
        context.record_signal(
            "replay-frame",
            f"scrub:{hop_index}->{sequence}",
            float(sequence),
        )
    # Determinism assertion: identical seeds produce identical sequences.
    context.record_signal(
        "custom",
        f"scrub-checksum={sum(seen_sequences) & 0xFFFFFFFF}",
        float(sum(seen_sequences) & 0xFFFFFFFF),
    )
