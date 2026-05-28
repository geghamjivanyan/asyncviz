from __future__ import annotations

import uuid


def new_task_id() -> str:
    """Generate a runtime-unique, replay-friendly task identifier.

    UUID4 hex (32 chars). Cheap to produce, stable across process restarts
    when persisted, and distinct from :func:`id()` which Python may reuse
    after garbage collection.
    """
    return uuid.uuid4().hex
