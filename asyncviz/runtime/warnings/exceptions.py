from __future__ import annotations


class WarningSystemError(Exception):
    """Base class for every :class:`RuntimeWarningManager` failure."""


class UnknownWarningError(WarningSystemError):
    """Raised by strict reads against a non-existent ``warning_id``."""


class DetectorRegistrationError(WarningSystemError):
    """Raised on duplicate / invalid detector registration."""


class WarningRebuildError(WarningSystemError):
    """Raised when :meth:`RuntimeWarningManager.rebuild` finds corrupted input."""
