"""Serialize a :class:`ReplayFrame` into the on-disk NDJSON shape.

Keeping serialization separate from the writer lets us reuse the
same shape elsewhere (in-memory replay → disk export) without
binding to file-IO.
"""

from __future__ import annotations

import json
from typing import Any

from asyncviz.runtime.replay.frames import ReplayFrame

#: Canonical JSON encoding options. ``separators`` removes whitespace
#: so NDJSON lines are compact; ``ensure_ascii=False`` keeps non-ASCII
#: task names readable in the on-disk artifact.
_JSON_KWARGS: dict[str, Any] = {
    "ensure_ascii": False,
    "separators": (",", ":"),
    "sort_keys": True,
}


def serialize_frame(frame: ReplayFrame) -> bytes:
    """Encode ``frame`` as one NDJSON line (trailing ``\\n``).

    Returns ``bytes`` because the writer streams to a binary file
    handle (gzip-wrapped or raw). Sorting keys keeps the output
    byte-stable for replay-determinism testing.
    """
    record = frame.as_dict()
    line = json.dumps(record, **_JSON_KWARGS)
    return (line + "\n").encode("utf-8")
