from __future__ import annotations

import threading

from asyncviz.runtime.clock.exceptions import ClockSequenceOverflowError

#: Hard ceiling — well past any practical event rate, but guards against
#: pathological runaway producers and matches the i64 frontends expect.
MAX_SEQUENCE: int = (1 << 63) - 1


class SequenceGenerator:
    """Thread-safe monotonically-increasing 64-bit sequence counter.

    The first allocated value is ``1`` — ``0`` is reserved as "no sequence
    issued yet" so consumers can tell the difference between *before any
    event* and *the very first event*.
    """

    __slots__ = ("_lock", "_max", "_value")

    def __init__(self, *, start: int = 0, max_value: int = MAX_SEQUENCE) -> None:
        if start < 0:
            raise ValueError("start must be non-negative")
        if max_value <= start:
            raise ValueError("max_value must exceed start")
        self._lock = threading.Lock()
        self._value = start
        self._max = max_value

    @property
    def current(self) -> int:
        with self._lock:
            return self._value

    def next(self) -> int:
        """Allocate and return the next sequence number. Always strictly increasing."""
        with self._lock:
            if self._value >= self._max:
                raise ClockSequenceOverflowError(
                    f"sequence exhausted at {self._value} (max={self._max})"
                )
            self._value += 1
            return self._value

    def reset(self) -> None:
        """Reset to zero. Intended for tests only — do not call in production."""
        with self._lock:
            self._value = 0
