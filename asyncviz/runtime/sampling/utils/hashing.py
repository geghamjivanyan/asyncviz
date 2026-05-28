"""Deterministic sampling hash.

The sampler's "should I keep this event?" decision uses a stable
hash of ``(event_type, sequence, seed)`` mapped to a bucket in
``[0, 1024)``. The same triple always produces the same bucket so:

* Replay of the same recording samples the same events.
* Federated runtimes agree on which events get dropped.
* Tests can assert exact bucket counts.

We use Python's :func:`hash` is *not* an option — its salt randomizes
between processes. ``hashlib.blake2b`` is deterministic, cheap, and
already in the stdlib.
"""

from __future__ import annotations

import hashlib

BUCKET_COUNT = 1024
"""Number of buckets in the sampling space. Powers of two give the
cheapest modulo arithmetic."""


def sampling_key(event_type: str, sequence: int, seed: int) -> bytes:
    """Produce the stable byte string the bucket hash chews on."""
    return (
        f"{seed}|{event_type}|{sequence}".encode()
    )


def deterministic_bucket(
    event_type: str, sequence: int, *, seed: int = 0xA5_BE_F7,
) -> int:
    """Map ``(event_type, sequence)`` to one of ``BUCKET_COUNT`` buckets."""
    key = sampling_key(event_type, sequence, seed)
    digest = hashlib.blake2b(key, digest_size=4).digest()
    # 32-bit unsigned integer → bucket
    value = int.from_bytes(digest, "big")
    return value % BUCKET_COUNT
