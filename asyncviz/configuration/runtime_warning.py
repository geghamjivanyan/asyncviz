"""Runtime warning-system options.

Today the warning manager and blocking-warning emitter ship with
defaults baked into their respective configuration classes. This
struct surfaces the operator-facing knobs so a future config-file or
profile can override them without reaching into the emitter
internals.
"""

from __future__ import annotations

from dataclasses import dataclass

from asyncviz.configuration.runtime_defaults import (
    DEFAULT_BLOCKING_COOLDOWN_MS,
    DEFAULT_WARNING_BUFFER,
)


@dataclass(frozen=True, slots=True)
class WarningOptions:
    """Warning-manager + blocking-warning emitter knobs."""

    buffer_size: int = DEFAULT_WARNING_BUFFER
    blocking_cooldown_ms: float = DEFAULT_BLOCKING_COOLDOWN_MS
