"""Signal-stream fingerprinting.

Determinism + uvloop-parity validation reduces to: "do two runs
produce the same signal stream?" The fingerprint is a stable hash of
the ``(kind, detail)`` tuples (values are NOT included — float
jitter from timing is acceptable on the boundary). Returns a
hex digest plus a structured breakdown for diagnostics.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

from tests.integration.harness.scenario_context import IntegrationSignal


@dataclass(frozen=True, slots=True)
class SignalFingerprint:
    digest: str
    signal_count: int
    by_kind: dict[str, int]


def fingerprint_signals(signals: Iterable[IntegrationSignal]) -> SignalFingerprint:
    hasher = hashlib.blake2b(digest_size=16)
    by_kind: dict[str, int] = {}
    count = 0
    for signal in signals:
        line = f"{signal.kind}\x00{signal.detail}".encode()
        hasher.update(line)
        hasher.update(b"\n")
        by_kind[signal.kind] = by_kind.get(signal.kind, 0) + 1
        count += 1
    return SignalFingerprint(
        digest=hasher.hexdigest(),
        signal_count=count,
        by_kind=by_kind,
    )


def signals_match(
    a: Iterable[IntegrationSignal],
    b: Iterable[IntegrationSignal],
) -> bool:
    return fingerprint_signals(a).digest == fingerprint_signals(b).digest
