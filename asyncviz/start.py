"""Backward-compatible entrypoint.

The real implementation lives in :mod:`asyncviz.bootstrap`. This module is
preserved so ``from asyncviz.start import start`` keeps working.
"""

from asyncviz.bootstrap import get_runtime, is_running, start, stop

__all__ = ["get_runtime", "is_running", "start", "stop"]
