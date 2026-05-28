"""Payload-type registry — pluggable encode/decode for frame payloads.

A frame's wire envelope is fixed (see :class:`ReplayFrame`), but the
*payload* field is a free-form dict whose shape depends on
``payload_type``. The registry binds a ``payload_type`` string to a
pair of functions:

* ``encode(value) -> dict`` — turns a domain object into a JSON-safe
  dict.
* ``decode(dict) -> value`` — reverses it.

If no decoder is registered for a payload type, the dict is returned
as-is. That guarantees forward compatibility: a reader receiving a
frame whose ``payload_type`` it doesn't know about still gets a
useful, routable :class:`ReplayFrame`.

The runtime-event payloads are auto-registered against
:data:`EVENT_REGISTRY` from the runtime event models — bringing a new
event type online doesn't require touching this module.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from asyncviz.runtime.events.models.serialization import (
    EVENT_REGISTRY,
    EventValidationError,
    from_dict as _runtime_event_from_dict,
    to_dict as _runtime_event_to_dict,
)


@dataclass(frozen=True, slots=True)
class PayloadCodec:
    """Encoder/decoder pair for one payload type."""

    payload_type: str
    encode: Callable[[Any], dict[str, Any]]
    decode: Callable[[dict[str, Any]], Any]
    """If decode raises, the registry's safe wrapper logs and falls
    back to returning the raw dict so corrupt entries don't kill the
    whole replay stream."""


class PayloadRegistry:
    """Process-wide registry of payload codecs.

    Thread-safe; writes go through a lock so a late-registered codec
    can't be observed half-installed by a concurrent decode."""

    __slots__ = ("_codecs", "_lock")

    def __init__(self) -> None:
        self._codecs: dict[str, PayloadCodec] = {}
        self._lock = threading.RLock()

    def register(self, codec: PayloadCodec) -> None:
        with self._lock:
            # Normalize keys to plain str so enum vs str callers
            # always look up the same codec.
            self._codecs[str(codec.payload_type)] = codec

    def unregister(self, payload_type: str) -> None:
        with self._lock:
            self._codecs.pop(str(payload_type), None)

    def get(self, payload_type: str) -> PayloadCodec | None:
        with self._lock:
            return self._codecs.get(str(payload_type))

    def has(self, payload_type: str) -> bool:
        with self._lock:
            return str(payload_type) in self._codecs

    def known_types(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._codecs))

    def reset(self) -> None:
        """Re-install only the built-in codecs. Tests use this."""
        with self._lock:
            self._codecs.clear()
        _install_builtin_codecs(self)


_REGISTRY: PayloadRegistry | None = None
_REGISTRY_LOCK = threading.Lock()


def get_payload_registry() -> PayloadRegistry:
    """Return the process-wide payload registry, building it on
    first access. The double-checked lock avoids the worst-case
    ``threading.Lock`` cost on every call."""
    global _REGISTRY
    if _REGISTRY is None:
        with _REGISTRY_LOCK:
            if _REGISTRY is None:
                registry = PayloadRegistry()
                _install_builtin_codecs(registry)
                _REGISTRY = registry
    return _REGISTRY


# ── built-in codecs ───────────────────────────────────────────────


def _runtime_event_codec(payload_type: str) -> PayloadCodec:
    def encode(event: Any) -> dict[str, Any]:
        return _runtime_event_to_dict(event)

    def decode(data: dict[str, Any]) -> Any:
        try:
            return _runtime_event_from_dict(data)
        except EventValidationError:
            # Forward-compat fallback: if the registered class can't
            # validate the payload (e.g. a new field arrived from a
            # newer producer), give the caller the raw dict instead
            # of raising and breaking the whole replay stream.
            return data

    return PayloadCodec(payload_type=payload_type, encode=encode, decode=decode)


def _passthrough_codec(payload_type: str) -> PayloadCodec:
    return PayloadCodec(
        payload_type=payload_type,
        encode=lambda value: dict(value) if isinstance(value, dict) else {"value": value},
        decode=lambda data: data,
    )


def _install_builtin_codecs(registry: PayloadRegistry) -> None:
    for event_type in EVENT_REGISTRY:
        registry.register(_runtime_event_codec(str(event_type)))
    # Snapshot/marker/metadata/diagnostics use pass-through codecs by
    # default — the producer owns the shape.
    for payload_type in (
        "snapshot.begin",
        "snapshot.end",
        "snapshot.delta",
        "metadata.recording",
        "metadata.runtime",
        "metadata.schema",
        "diagnostics.summary",
    ):
        registry.register(_passthrough_codec(payload_type))


def reset_payload_registry() -> None:
    """Test helper. Wipes user-installed codecs and re-installs
    built-ins."""
    if _REGISTRY is None:
        return
    _REGISTRY.reset()
