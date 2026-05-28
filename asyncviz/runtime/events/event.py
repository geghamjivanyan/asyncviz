"""Backward-compat re-export.

The canonical event-model layer lives in :mod:`asyncviz.runtime.events.models`.
This module preserves the older import path so existing call sites continue
to work.
"""

from asyncviz.runtime.events.models import GenericEvent, RuntimeEvent

__all__ = ["GenericEvent", "RuntimeEvent"]
