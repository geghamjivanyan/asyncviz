"""String-interner tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.memory import StringInterner


def test_intern_returns_same_instance() -> None:
    interner = StringInterner(capacity=16)
    a = interner.intern("asyncio.task.created")
    b = interner.intern("asyncio.task.created")
    assert a is b


def test_intern_different_strings_return_different_instances() -> None:
    interner = StringInterner(capacity=16)
    a = interner.intern("alpha")
    b = interner.intern("beta")
    assert a != b


def test_intern_capacity_bypasses_overflow() -> None:
    interner = StringInterner(capacity=3)
    for i in range(3):
        interner.intern(f"k-{i}")
    # 4th unique entry should *not* be added — interner returns the
    # raw string without storing it.
    interner.intern("k-4")
    stats = interner.stats()
    assert stats.size == 3
    assert stats.bypassed == 1


def test_intern_many_returns_canonical_tuple() -> None:
    interner = StringInterner(capacity=16)
    out = interner.intern_many(("a", "b", "a"))
    assert out[0] is out[2]
    assert out[1] != out[0]


def test_stats_track_hits_and_misses() -> None:
    interner = StringInterner(capacity=4)
    interner.intern("x")
    interner.intern("x")
    interner.intern("y")
    stats = interner.stats()
    assert stats.hits == 1
    assert stats.misses == 2


def test_clear_resets() -> None:
    interner = StringInterner(capacity=4)
    interner.intern("alpha")
    interner.clear()
    assert interner.stats().size == 0
    # After clear, intern again — should be a miss (not a hit).
    interner.intern("alpha")
    assert interner.stats().misses == 1


def test_intern_rejects_non_string() -> None:
    interner = StringInterner(capacity=4)
    with pytest.raises(TypeError):
        interner.intern(42)  # type: ignore[arg-type]
