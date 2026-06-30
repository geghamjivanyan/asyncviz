"""Version compatibility + payload migration registry.

The wire envelope is versioned by :data:`SCHEMA_VERSION`. The
*payload* schema is versioned independently by the runtime event
protocol. This module bridges the two with three concrete behaviors:

1. **Envelope acceptance gate** — given a frame's reported envelope
   version, decide whether this reader can decode it at all.
2. **Forward compatibility** — additive payload fields land in the
   raw dict; nothing is dropped, even if the running reader doesn't
   know about a key yet. (Implemented in
   :mod:`ndjson_deserialization` + :mod:`ndjson_frame`.)
3. **Deterministic upgrade** — when a payload-version migration is
   registered, applying it must always produce the same output for
   the same input. Migrations form a chain: ``v1 → v2 → v3``.

Migrations are deliberately optional: most evolution is additive,
which doesn't need a migration step. Migrations exist for the rare
cases where a payload's shape changed in a way readers can't muddle
through (e.g. a field was split into two).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from asyncviz.replay.format.ndjson_schema import (
    MIN_READABLE_SCHEMA_VERSION,
    SCHEMA_VERSION,
)


class VersioningError(ValueError):
    """Raised when a frame's version cannot be reconciled with the
    current reader's capabilities."""


@dataclass(frozen=True, slots=True)
class CompatibilityVerdict:
    """Result of an envelope version check."""

    compatible: bool
    envelope_version: int
    reader_version: int
    reason: str = ""

    def raise_if_incompatible(self) -> None:
        if not self.compatible:
            raise VersioningError(
                f"envelope schema_version={self.envelope_version} not readable "
                f"by reader v{self.reader_version}: {self.reason}",
            )


def check_envelope_compatibility(envelope_version: int) -> CompatibilityVerdict:
    """Decide whether a frame at ``envelope_version`` can be decoded
    by this reader."""
    if envelope_version < MIN_READABLE_SCHEMA_VERSION:
        return CompatibilityVerdict(
            compatible=False,
            envelope_version=envelope_version,
            reader_version=SCHEMA_VERSION,
            reason=(f"too old; reader requires >= {MIN_READABLE_SCHEMA_VERSION}"),
        )
    if envelope_version > SCHEMA_VERSION:
        # Newer envelope — tolerate by best-effort decode, but flag
        # the version skew. Readers can still consume the frame; any
        # unknown envelope keys land in ``extensions``.
        return CompatibilityVerdict(
            compatible=True,
            envelope_version=envelope_version,
            reader_version=SCHEMA_VERSION,
            reason="newer envelope tolerated via additive forward-compat",
        )
    return CompatibilityVerdict(
        compatible=True,
        envelope_version=envelope_version,
        reader_version=SCHEMA_VERSION,
    )


# ── payload migration registry ────────────────────────────────────

PayloadMigration = Callable[[dict[str, Any]], dict[str, Any]]
"""Single-step migration: dict in, dict out. Must be deterministic
and idempotent on its own output."""


@dataclass(frozen=True, slots=True)
class MigrationKey:
    """Identifies one migration step in the chain."""

    payload_type: str
    from_version: int
    to_version: int


class MigrationRegistry:
    """Process-wide payload migration registry."""

    __slots__ = ("_lock", "_steps")

    def __init__(self) -> None:
        self._steps: dict[MigrationKey, PayloadMigration] = {}
        self._lock = threading.RLock()

    def register(self, key: MigrationKey, migration: PayloadMigration) -> None:
        if key.from_version >= key.to_version:
            raise ValueError(
                f"migration {key.payload_type} must move forward "
                f"(from={key.from_version} to={key.to_version})",
            )
        with self._lock:
            self._steps[key] = migration

    def migrate(
        self,
        payload_type: str,
        payload: dict[str, Any],
        from_version: int,
        to_version: int,
    ) -> dict[str, Any]:
        """Apply the chain of registered migrations to walk a payload
        from ``from_version`` to ``to_version``. Returns the original
        payload unchanged if no migration is registered for a step —
        that's the forward-compat path."""
        if from_version >= to_version:
            return payload
        current = dict(payload)
        with self._lock:
            steps = dict(self._steps)
        version = from_version
        while version < to_version:
            key = MigrationKey(
                payload_type=payload_type,
                from_version=version,
                to_version=version + 1,
            )
            migration = steps.get(key)
            if migration is None:
                # No migration step — assume additive forward-compat.
                version += 1
                continue
            current = migration(current)
            if not isinstance(current, dict):
                raise VersioningError(
                    f"migration {key} returned non-dict: {type(current).__name__}",
                )
            version += 1
        return current

    def known_steps(self) -> tuple[MigrationKey, ...]:
        with self._lock:
            return tuple(sorted(self._steps, key=lambda k: (k.payload_type, k.from_version)))

    def reset(self) -> None:
        with self._lock:
            self._steps.clear()


_MIGRATIONS: MigrationRegistry | None = None
_MIGRATIONS_LOCK = threading.Lock()


def get_migration_registry() -> MigrationRegistry:
    global _MIGRATIONS
    if _MIGRATIONS is None:
        with _MIGRATIONS_LOCK:
            if _MIGRATIONS is None:
                _MIGRATIONS = MigrationRegistry()
    return _MIGRATIONS


def reset_migration_registry() -> None:
    if _MIGRATIONS is not None:
        _MIGRATIONS.reset()
