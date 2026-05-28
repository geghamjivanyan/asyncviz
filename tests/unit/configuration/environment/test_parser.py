from __future__ import annotations

from pathlib import Path

import pytest

from asyncviz.configuration.environment.environment_parser import (
    parse_bool,
    parse_duration_ms,
    parse_duration_seconds,
    parse_enum,
    parse_float,
    parse_int,
    parse_list,
    parse_path,
    parse_string,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("FALSE", False),
        ("1", True),
        ("0", False),
        ("on", True),
        ("off", False),
        ("Yes", True),
        ("no", False),
    ],
)
def test_parse_bool_accepts_canonical_forms(raw: str, expected: bool) -> None:
    out = parse_bool(raw)
    assert out.ok
    assert out.value is expected


def test_parse_bool_rejects_garbage() -> None:
    out = parse_bool("yolo")
    assert not out.ok
    assert "yolo" in (out.error or "")


def test_parse_int_handles_negatives_and_whitespace() -> None:
    assert parse_int("  -42 ").value == -42


def test_parse_int_rejects_non_numeric() -> None:
    out = parse_int("abc")
    assert not out.ok


def test_parse_float_parses_scientific_notation() -> None:
    assert parse_float("1e-3").value == 1e-3


def test_parse_string_rejects_empty() -> None:
    out = parse_string("")
    assert not out.ok


@pytest.mark.parametrize(
    "raw,expected_seconds",
    [
        ("250ms", 0.25),
        ("5s", 5.0),
        ("1.5m", 90.0),
        ("0.25h", 900.0),
        ("3", 3.0),  # bare number → seconds
    ],
)
def test_parse_duration_seconds_handles_units(raw: str, expected_seconds: float) -> None:
    out = parse_duration_seconds(raw)
    assert out.ok
    assert out.value == pytest.approx(expected_seconds)


def test_parse_duration_seconds_rejects_unknown_unit() -> None:
    out = parse_duration_seconds("5xyz")
    assert not out.ok


def test_parse_duration_ms_converts_to_ms() -> None:
    out = parse_duration_ms("1s")
    assert out.ok
    assert out.value == 1000.0


def test_parse_path_expands_user_and_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", "/home/asyncviz")
    out = parse_path("~/replays/${UNSET_VAR_X}session.avz")
    assert out.ok
    assert isinstance(out.value, Path)
    assert "/home/asyncviz/replays" in str(out.value)


def test_parse_enum_preserves_canonical_casing() -> None:
    parser = parse_enum(choices=("DEBUG", "INFO", "WARNING"))
    out = parser("info")
    assert out.ok
    assert out.value == "INFO"


def test_parse_enum_rejects_unknown() -> None:
    parser = parse_enum(choices=("auto", "always", "never"))
    out = parser("YOLO")
    assert not out.ok
    assert "auto" in (out.error or "")


def test_parse_list_splits_and_trims() -> None:
    parser = parse_list(separator=",")
    out = parser("a, b ,c")
    assert out.ok
    assert out.value == ("a", "b", "c")


def test_parse_list_empty_returns_empty_tuple() -> None:
    parser = parse_list()
    out = parser("")
    assert out.ok
    assert out.value == ()
