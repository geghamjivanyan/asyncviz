"""Shared fixtures for sampling tests."""

from __future__ import annotations

import pytest

from asyncviz.runtime.sampling import (
    EventSampler,
    SamplingConfig,
    aggressive_config,
    clear_sampling_trace,
    default_config,
    off_config,
    reset_sampling_metrics,
    set_sampling_trace_enabled,
)


@pytest.fixture(autouse=True)
def _reset_sampling_globals() -> None:
    reset_sampling_metrics()
    clear_sampling_trace()
    set_sampling_trace_enabled(False)


@pytest.fixture
def default_sampler() -> EventSampler:
    return EventSampler(default_config())


@pytest.fixture
def aggressive_sampler() -> EventSampler:
    return EventSampler(aggressive_config())


@pytest.fixture
def off_sampler() -> EventSampler:
    return EventSampler(off_config())


@pytest.fixture
def custom_sampler() -> EventSampler:
    # Predictable rates for deterministic-percentage tests.
    return EventSampler(
        SamplingConfig(
            state_retention=0.5,
            delta_retention=0.1,
            budget_target_events=1_000_000,  # never trip
        ),
    )
