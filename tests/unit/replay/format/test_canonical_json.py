"""Canonical JSON encoding determinism tests."""

from __future__ import annotations

import math

import pytest

from asyncviz.replay.format.utils.canonical_json import (
    CanonicalEncodingError,
    canonical_dumps,
    canonical_loads,
    sort_mapping,
)


def test_canonical_dumps_sorts_keys() -> None:
    assert canonical_dumps({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_canonical_dumps_no_whitespace() -> None:
    out = canonical_dumps({"x": [1, 2, {"y": 3}]})
    assert " " not in out
    assert out == '{"x":[1,2,{"y":3}]}'


def test_canonical_dumps_deterministic_across_calls() -> None:
    payload = {"z": [3, 1, 2], "a": {"q": 1, "p": 2}, "m": "hello"}
    assert canonical_dumps(payload) == canonical_dumps(payload)


def test_sort_mapping_normalizes_nested_dicts() -> None:
    raw = {"b": {"d": 1, "c": 2}, "a": [3, {"f": 4, "e": 5}]}
    sorted_form = sort_mapping(raw)
    assert list(sorted_form.keys()) == ["a", "b"]
    assert list(sorted_form["b"].keys()) == ["c", "d"]
    # Lists keep order; the dict inside them is normalized.
    assert sorted_form["a"][0] == 3
    assert list(sorted_form["a"][1].keys()) == ["e", "f"]


def test_canonical_dumps_rejects_inf() -> None:
    with pytest.raises(CanonicalEncodingError):
        canonical_dumps({"x": math.inf})


def test_canonical_dumps_rejects_nan() -> None:
    with pytest.raises(CanonicalEncodingError):
        canonical_dumps({"x": math.nan})


def test_canonical_loads_round_trip() -> None:
    raw = {"a": 1, "b": [1, 2, 3], "c": {"d": True}}
    assert canonical_loads(canonical_dumps(raw)) == raw
