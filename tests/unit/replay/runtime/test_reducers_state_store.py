"""Reducers + state store tests."""

from __future__ import annotations

from asyncviz.replay.format import ReplayFrame
from asyncviz.replay.runtime import (
    ReducerRegistry,
    ReplayStateStore,
    VirtualRuntimeState,
    domain_reducer,
)


def _frame(
    seq: int,
    payload_type: str = "asyncio.task.created",
    task_id: str = "t-1",
) -> ReplayFrame:
    return ReplayFrame.for_runtime_event(
        sequence=seq,
        monotonic_ns=seq * 10,
        payload_type=payload_type,
        payload={"task_id": task_id},
    )


def test_default_reducer_advances_counters() -> None:
    registry = ReducerRegistry()
    state = registry.apply(VirtualRuntimeState.empty(), _frame(1))
    assert state.last_sequence == 1
    assert state.frames_applied == 1


def test_registered_reducer_applies_after_default() -> None:
    registry = ReducerRegistry()

    def task_reducer(domain: dict, frame: ReplayFrame) -> dict:
        domain[frame.payload["task_id"]] = True
        return domain

    registry.register(
        "asyncio.task.created",
        domain_reducer("tasks", apply=task_reducer),
    )
    state = registry.apply(VirtualRuntimeState.empty(), _frame(1, task_id="t-1"))
    state = registry.apply(state, _frame(2, task_id="t-2"))
    assert state.frames_applied == 2
    assert state.domains["tasks"] == {"t-1": True, "t-2": True}


def test_unknown_payload_type_only_runs_default() -> None:
    registry = ReducerRegistry()
    state = registry.apply(VirtualRuntimeState.empty(), _frame(1, payload_type="x.unknown"))
    assert state.last_sequence == 1
    assert state.domains == {}


def test_state_store_update_swaps_atomically() -> None:
    store = ReplayStateStore()
    received = []
    store.subscribe(lambda prev, nxt: received.append((prev, nxt)))
    new_state = store.update(lambda s: s.with_advance(sequence=1, monotonic_ns=10))
    assert new_state.last_sequence == 1
    assert len(received) == 1
    assert received[0][0].last_sequence == 0
    assert received[0][1].last_sequence == 1


def test_state_store_update_no_op_does_not_swap() -> None:
    store = ReplayStateStore()
    received = []
    store.subscribe(lambda prev, nxt: received.append((prev, nxt)))
    store.update(lambda s: s)  # identity
    assert received == []


def test_state_store_replace_overrides_listener_invoked() -> None:
    store = ReplayStateStore()
    received = []
    store.subscribe(lambda prev, nxt: received.append((prev, nxt)))
    new_state = VirtualRuntimeState(
        last_sequence=42,
        last_monotonic_ns=420,
        frames_applied=1,
    )
    store.replace(new_state)
    assert store.state.last_sequence == 42
    assert len(received) == 1


def test_state_listener_exception_does_not_break_store() -> None:
    store = ReplayStateStore()

    def boom(prev, nxt):
        raise RuntimeError("noisy listener")

    store.subscribe(boom)
    # Should not raise.
    store.update(lambda s: s.with_advance(sequence=1, monotonic_ns=1))
    assert store.state.last_sequence == 1
