from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Coroutine
from typing import Any


def extract_coroutine_name(coro: Coroutine[Any, Any, Any]) -> str | None:
    """Return the most informative coroutine name we can find cheaply.

    Order of preference:
    1. ``coro.cr_code.co_qualname`` (Python 3.11+) — includes class scope.
    2. ``coro.cr_code.co_name``      — bare function name.
    3. ``coro.__qualname__`` / ``coro.__name__`` — for wrapped/special types.
    """
    with contextlib.suppress(Exception):
        code = getattr(coro, "cr_code", None)
        if code is not None:
            return getattr(code, "co_qualname", None) or getattr(code, "co_name", None)
        return getattr(coro, "__qualname__", None) or getattr(coro, "__name__", None)
    return None


def extract_module(coro: Coroutine[Any, Any, Any]) -> str | None:
    with contextlib.suppress(Exception):
        code = getattr(coro, "cr_code", None)
        if code is not None:
            return getattr(code, "co_filename", None)
    return None


def extract_task_name(task: asyncio.Task[Any]) -> str | None:
    with contextlib.suppress(Exception):
        return task.get_name()
    return None
