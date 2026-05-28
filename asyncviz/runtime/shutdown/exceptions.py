from __future__ import annotations


class ShutdownError(Exception):
    """Base class for every :class:`RuntimeShutdownCoordinator` failure."""


class ShutdownAlreadyRunningError(ShutdownError):
    """Raised when :meth:`RuntimeShutdownCoordinator.run` is invoked twice.

    The coordinator's external API is :meth:`request_shutdown` (idempotent);
    :meth:`run` is the internal entrypoint and is *not* safe to enter
    concurrently. This error lets misuse surface loudly in tests rather
    than silently hanging on the second await.
    """


class ShutdownTimeoutError(ShutdownError):
    """Raised by an internal step when its bounded operation overshoots.

    The coordinator catches it, records a timeout in
    :class:`ShutdownReport`, escalates to the next step, and resumes —
    timeouts are operational events, not fatal errors.
    """


class ShutdownNotCompletedError(ShutdownError):
    """Raised when ``report()`` is called before the coordinator finished.

    Reports are read-only post-shutdown views; trying to read one
    mid-flight would expose inconsistent partial values.
    """
