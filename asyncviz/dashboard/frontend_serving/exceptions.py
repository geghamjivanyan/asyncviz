from __future__ import annotations


class FrontendServingError(Exception):
    """Base class for every :class:`FrontendServingService` failure."""


class FrontendBundleMissingError(FrontendServingError):
    """Raised when ``frontend_mode=embedded`` but no bundle is on disk.

    The pre-flight validation in :mod:`asyncviz.bootstrap.validation`
    catches this at startup with a friendly hint to run
    ``make embed-frontend``. The runtime path raises this for
    programmatic callers (tests, custom embeddings) so failures are
    typed rather than silent.
    """


class ManifestLoadError(FrontendServingError):
    """Raised when a Vite manifest is present but unparseable.

    The service falls back to filesystem discovery on any manifest
    error — this is logged as a degradation, not a fatal startup
    failure, because a corrupted manifest shouldn't take down the
    dashboard.
    """


class PathTraversalRejectedError(FrontendServingError):
    """Raised by :class:`AssetResolver` when a request path escapes the static root.

    Normally callers don't see this — the service translates it into
    an HTTP 404. Surfaced as a typed error so probes / tests can
    assert on the rejection path without parsing logs.
    """
