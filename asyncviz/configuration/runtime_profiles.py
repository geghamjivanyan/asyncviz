"""Named runtime profiles.

Profiles are pre-baked option bundles for common deployment shapes:

* ``"dev"``     — developer laptop default; verbose logs, browser open.
* ``"prod"``    — production embed; quiet logs, no browser, longer
  retention.
* ``"ci"``      — CI/test runners; minimal logging, no browser,
  recording optional.

A profile *seeds* the resolver — environment / CLI / API kwargs still
override profile values. Lives in its own module so plugin packages
can register additional profiles later via
:func:`register_profile`.
"""

from __future__ import annotations

from collections.abc import Callable

from asyncviz.configuration.runtime_browser import BrowserOptions
from asyncviz.configuration.runtime_dashboard import DashboardOptions
from asyncviz.configuration.runtime_monitoring import MonitoringOptions
from asyncviz.configuration.runtime_options import RuntimeOptions
from asyncviz.configuration.runtime_replay import ReplayOptions

ProfileFactory = Callable[[], RuntimeOptions]

_REGISTRY: dict[str, ProfileFactory] = {}


def _dev_profile() -> RuntimeOptions:
    return RuntimeOptions(
        dashboard=DashboardOptions(debug=True, log_level="DEBUG"),
        browser=BrowserOptions(policy="auto"),
        profile_name="dev",
    )


def _prod_profile() -> RuntimeOptions:
    return RuntimeOptions(
        dashboard=DashboardOptions(log_level="WARNING"),
        browser=BrowserOptions(policy="never"),
        replay=ReplayOptions(retention_seconds=3600.0, buffer_capacity=32_768),
        profile_name="prod",
    )


def _ci_profile() -> RuntimeOptions:
    return RuntimeOptions(
        dashboard=DashboardOptions(log_level="WARNING"),
        browser=BrowserOptions(policy="never"),
        monitoring=MonitoringOptions(capture_stack_traces=False),
        profile_name="ci",
    )


_REGISTRY["dev"] = _dev_profile
_REGISTRY["prod"] = _prod_profile
_REGISTRY["ci"] = _ci_profile


def list_profile_names() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def get_profile(name: str) -> RuntimeOptions:
    """Return the profile named ``name``. Raises ``KeyError`` when unknown."""
    try:
        factory = _REGISTRY[name.lower()]
    except KeyError as exc:
        raise KeyError(
            f"unknown profile {name!r}; known: {list_profile_names()}",
        ) from exc
    return factory()


def register_profile(name: str, factory: ProfileFactory) -> None:
    """Register a plugin-supplied profile. Overrides built-ins."""
    _REGISTRY[name.lower()] = factory
