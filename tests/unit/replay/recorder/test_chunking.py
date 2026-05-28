from __future__ import annotations

from asyncviz.runtime.replay.recorder.replay_chunking import ChunkPolicy


def test_chunk_policy_rolls_on_event_threshold() -> None:
    policy = ChunkPolicy(max_events=3, max_bytes=0)
    for _ in range(3):
        policy.record(10)
    assert policy.should_roll()
    policy.reset_for_new_chunk()
    assert not policy.should_roll()


def test_chunk_policy_rolls_on_byte_threshold() -> None:
    policy = ChunkPolicy(max_events=0, max_bytes=100)
    policy.record(50)
    assert not policy.should_roll()
    policy.record(50)
    assert policy.should_roll()


def test_chunk_policy_no_roll_when_empty() -> None:
    policy = ChunkPolicy(max_events=0, max_bytes=0)
    assert not policy.should_roll()
    policy.record(1)
    # Both thresholds disabled — never rolls.
    assert not policy.should_roll()


def test_chunk_policy_reset_resets_counters() -> None:
    policy = ChunkPolicy(max_events=2, max_bytes=0)
    policy.record(1)
    policy.record(1)
    assert policy.should_roll()
    policy.reset_for_new_chunk()
    assert policy.events_in_chunk == 0
    assert policy.bytes_in_chunk == 0
    assert policy.chunks_rolled == 1
