"""Deterministic RNG for stress workloads.

A thin wrapper around :class:`random.Random` so every stress
component shares the same well-defined seeding model. The RNG is
*not* synchronized — each scenario should construct its own to avoid
contention. Identical seeds + identical call sequences yield
identical streams (the foundation of replay-safe stress testing).
"""

from __future__ import annotations

import random
from collections.abc import Iterable
from typing import TypeVar

T = TypeVar("T")


class DeterministicRng:
    """Wrapper around :class:`random.Random` with a documented surface."""

    __slots__ = ("_rng", "_seed")

    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._rng = random.Random(seed)

    @property
    def seed(self) -> int:
        return self._seed

    def fraction(self) -> float:
        """Next float in [0.0, 1.0)."""
        return self._rng.random()

    def integer(self, lo: int, hi: int) -> int:
        """Inclusive integer in ``[lo, hi]``."""
        return self._rng.randint(lo, hi)

    def choice(self, sequence: list[T] | tuple[T, ...]) -> T:
        return self._rng.choice(sequence)

    def shuffled(self, sequence: Iterable[T]) -> list[T]:
        items = list(sequence)
        self._rng.shuffle(items)
        return items

    def coin(self, probability: float) -> bool:
        """``True`` with the given probability, deterministic."""
        if probability <= 0.0:
            return False
        if probability >= 1.0:
            return True
        return self._rng.random() < probability

    def jitter(self, value: float, ratio: float) -> float:
        """Return ``value`` perturbed by up to ``±value * ratio``."""
        if ratio <= 0:
            return value
        delta = self._rng.uniform(-value * ratio, value * ratio)
        return value + delta
