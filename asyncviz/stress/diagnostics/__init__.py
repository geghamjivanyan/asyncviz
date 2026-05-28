"""Stress diagnostics subpackage.

This subpackage exists as a sibling of :mod:`stress_diagnostics` so
external dashboards can ``from asyncviz.stress.diagnostics import …``
without importing the top-level façade. The single re-export keeps
the package non-empty (Python skips empty namespace packages in some
distribution tooling) without creating two parallel APIs.
"""

from asyncviz.stress.stress_diagnostics import (
    StressDiagnostics,
    build_stress_diagnostics,
)

__all__ = ["StressDiagnostics", "build_stress_diagnostics"]
