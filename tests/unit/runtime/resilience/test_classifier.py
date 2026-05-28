"""Failure classifier tests."""

from __future__ import annotations

import asyncio

import pytest

from asyncviz.runtime.resilience import (
    FailureKind,
    classify_exception,
    classify_marker,
)


@pytest.mark.parametrize(
    "exc, expected",
    [
        (asyncio.CancelledError(), FailureKind.CANCELLED),
        (AssertionError("x"), FailureKind.PROGRAMMER),
        (TypeError("x"), FailureKind.PROGRAMMER),
        (MemoryError("x"), FailureKind.RESOURCE),
        (TimeoutError("x"), FailureKind.TRANSIENT),
        (ConnectionResetError("x"), FailureKind.TRANSIENT),
        (ValueError("corrupted-frame: bad checksum"), FailureKind.CORRUPTION),
        (RuntimeError("websocket handshake failed"), FailureKind.PROTOCOL),
        (RuntimeError("out of memory"), FailureKind.RESOURCE),
        (RuntimeError("totally unknown error"), FailureKind.UNKNOWN),
    ],
)
def test_classify_exception(exc: BaseException, expected: FailureKind) -> None:
    assert classify_exception(exc) == expected


def test_enospc_is_resource() -> None:
    exc = OSError(28, "no space left on device")
    assert classify_exception(exc) == FailureKind.RESOURCE


@pytest.mark.parametrize(
    "marker, expected",
    [
        ("cancelled", FailureKind.CANCELLED),
        ("checksum-mismatch", FailureKind.CORRUPTION),
        ("websocket-protocol-violation", FailureKind.PROTOCOL),
        ("disk-full", FailureKind.RESOURCE),
        ("operation-timeout", FailureKind.TRANSIENT),
        ("assert-failed", FailureKind.PROGRAMMER),
        ("totally-unknown", FailureKind.UNKNOWN),
    ],
)
def test_classify_marker(marker: str, expected: FailureKind) -> None:
    assert classify_marker(marker) == expected
