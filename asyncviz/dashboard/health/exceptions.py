from __future__ import annotations


class HealthError(Exception):
    """Base class for every :class:`HealthService` failure."""


class CheckExecutionError(HealthError):
    """Raised internally when a probe callback misbehaves.

    Probe functions are not supposed to raise — they catch their own
    exceptions and return an ``UNAVAILABLE`` :class:`HealthCheckResult`.
    This error covers the *probe registration* path (e.g. duplicate
    names) so the registry itself can fail loudly.
    """


class DuplicateProbeError(HealthError):
    """Raised when a probe name is registered twice."""
