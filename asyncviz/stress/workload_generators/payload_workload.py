"""Synthetic payload workload.

Produces deterministic byte payloads sized to feed websocket /
serialization / disk-I/O storms. The payloads are *interned* across
calls so generating 10k 1KiB payloads doesn't allocate 10MiB — the
generator returns the same ``bytes`` object when the requested size
matches a cached entry.
"""

from __future__ import annotations

from collections.abc import Iterator

_CACHE: dict[int, bytes] = {}


def stable_payload(size_bytes: int) -> bytes:
    """Return a deterministic byte payload of the requested size.

    Repeated calls with the same size return the *same* object —
    safe because payloads are immutable.
    """
    if size_bytes < 0:
        raise ValueError(f"size_bytes must be >= 0 (got {size_bytes})")
    cached = _CACHE.get(size_bytes)
    if cached is not None:
        return cached
    payload = bytes((i % 251) for i in range(size_bytes))
    _CACHE[size_bytes] = payload
    return payload


def generate_payload_storm(
    *,
    count: int,
    sizes: tuple[int, ...],
) -> Iterator[bytes]:
    """Yield ``count`` payloads cycling through ``sizes``.

    Useful for websocket-flood scenarios where heterogeneous payload
    sizes exercise the batcher / coalescer harder than identical
    ones.
    """
    if count < 0:
        raise ValueError(f"count must be >= 0 (got {count})")
    if not sizes:
        raise ValueError("sizes must be non-empty")
    for index in range(count):
        yield stable_payload(sizes[index % len(sizes)])


def reset_payload_cache() -> None:
    """Drop the interned-payload cache (used in tests)."""
    _CACHE.clear()
