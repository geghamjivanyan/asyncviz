"""Recovery-attempt outcome value."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RecoveryVerdict = Literal[
    "succeeded",
    "failed",
    "deferred",
    "abandoned",
    "skipped",
]


@dataclass(frozen=True, slots=True)
class RecoveryOutcome:
    subsystem: str
    attempt: int
    verdict: RecoveryVerdict
    duration_s: float
    detail: str = ""
