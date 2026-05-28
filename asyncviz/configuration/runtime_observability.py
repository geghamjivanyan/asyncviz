"""Process-wide counters for the runtime-options resolver."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigurationMetricsSnapshot:
    resolutions: int
    validations_passed: int
    validations_failed: int
    overrides_applied: int
    profile_loads: int
    environment_layers: int


class _ConfigurationMetrics:
    def __init__(self) -> None:
        self._resolutions = 0
        self._validations_passed = 0
        self._validations_failed = 0
        self._overrides_applied = 0
        self._profile_loads = 0
        self._environment_layers = 0

    def record_resolution(self) -> None:
        self._resolutions += 1

    def record_validation(self, *, ok: bool) -> None:
        if ok:
            self._validations_passed += 1
        else:
            self._validations_failed += 1

    def record_override(self, *, count: int = 1) -> None:
        if count > 0:
            self._overrides_applied += count

    def record_profile_load(self) -> None:
        self._profile_loads += 1

    def record_environment_layer(self) -> None:
        self._environment_layers += 1

    def snapshot(self) -> ConfigurationMetricsSnapshot:
        return ConfigurationMetricsSnapshot(
            resolutions=self._resolutions,
            validations_passed=self._validations_passed,
            validations_failed=self._validations_failed,
            overrides_applied=self._overrides_applied,
            profile_loads=self._profile_loads,
            environment_layers=self._environment_layers,
        )

    def reset(self) -> None:
        self.__init__()


_instance = _ConfigurationMetrics()


def get_configuration_metrics() -> _ConfigurationMetrics:
    return _instance


def reset_configuration_metrics() -> None:
    _instance.reset()
