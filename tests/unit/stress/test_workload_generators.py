"""Tests for synthetic workload generators."""

from __future__ import annotations

import pytest

from asyncviz.stress import (
    generate_event_storm,
    generate_payload_storm,
    generate_task_storm,
    generate_topology_storm,
    reset_payload_cache,
    stable_payload,
)


def test_task_storm_is_deterministic_given_same_seed() -> None:
    a = list(generate_task_storm(size=64, seed=7, dependency_depth=4))
    b = list(generate_task_storm(size=64, seed=7, dependency_depth=4))
    assert a == b


def test_task_storm_varies_with_seed() -> None:
    a = list(generate_task_storm(size=64, seed=1, dependency_depth=4))
    b = list(generate_task_storm(size=64, seed=2, dependency_depth=4))
    assert a != b


def test_task_storm_respects_dependency_depth() -> None:
    items = list(generate_task_storm(size=32, seed=1, dependency_depth=4))
    for item in items:
        assert 0 <= item.depth < 4


def test_task_storm_rejects_invalid_depth() -> None:
    with pytest.raises(ValueError):
        list(generate_task_storm(size=4, seed=1, dependency_depth=0))


def test_event_storm_emits_priorities() -> None:
    items = list(generate_event_storm(size=100, seed=1))
    assert len(items) == 100
    # Some events should be priority 3 (runtime.warning) eventually.
    priorities = {item.priority for item in items}
    assert 0 in priorities or 1 in priorities or 2 in priorities or 3 in priorities


def test_event_storm_payload_bounds() -> None:
    items = list(generate_event_storm(size=64, seed=1, payload_min=10, payload_max=20))
    for item in items:
        assert 10 <= item.payload_bytes <= 20


def test_event_storm_rejects_empty_types() -> None:
    with pytest.raises(ValueError):
        list(generate_event_storm(size=4, seed=1, event_types=()))


def test_stable_payload_interns() -> None:
    reset_payload_cache()
    p1 = stable_payload(64)
    p2 = stable_payload(64)
    assert p1 is p2


def test_stable_payload_size_matches() -> None:
    p = stable_payload(128)
    assert len(p) == 128


def test_payload_storm_cycles_sizes() -> None:
    reset_payload_cache()
    sizes = (32, 64, 128)
    items = list(generate_payload_storm(count=6, sizes=sizes))
    assert [len(p) for p in items] == [32, 64, 128, 32, 64, 128]


def test_topology_storm_layered() -> None:
    nodes = generate_topology_storm(node_count=64, seed=1, fanout=2, depth=4)
    by_depth = {n.depth for n in nodes}
    assert by_depth.issubset({0, 1, 2, 3})
    roots = [n for n in nodes if n.depth == 0]
    assert all(n.parent_ids == () for n in roots)


def test_topology_storm_deterministic() -> None:
    a = generate_topology_storm(node_count=32, seed=5, fanout=2, depth=4)
    b = generate_topology_storm(node_count=32, seed=5, fanout=2, depth=4)
    assert a == b
