"""Stress-scenario value model.

A *scenario* is the unit of work the :class:`StressRunner` executes.
Every scenario declares:

* a stable :attr:`name` (used by the registry + reports),
* a :attr:`category` bucket (task / websocket / replay / render / ...),
* an optional :attr:`severity` tier (selects defaults),
* whether it is :attr:`replay_safe` (deterministic across runs).

Scenarios are *values* — no callable embedded. The registry holds the
actual coroutine separately so the model stays trivially copy-able.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScenarioCategory = Literal[
    "task",
    "websocket",
    "replay",
    "render",
    "topology",
    "executor",
    "queue",
    "semaphore",
    "synthetic",
]

ScenarioSeverity = Literal["light", "moderate", "heavy", "extreme"]


@dataclass(frozen=True, slots=True)
class StressScenarioSpec:
    """Declarative description of a single stress scenario."""

    name: str
    category: ScenarioCategory
    severity: ScenarioSeverity = "moderate"
    description: str = ""
    replay_safe: bool = True
    failure_injection: bool = False
    """``True`` when the scenario expects failure injection to be applied."""
