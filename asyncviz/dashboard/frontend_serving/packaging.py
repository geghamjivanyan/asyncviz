"""Compatibility shim — embedded-package static-directory discovery.

The canonical asset-resolution lives in
:mod:`asyncviz.packaging.assets`. This module re-exports the narrow
"give me the static directory" helper so existing callers + tests
keep working without each one having to learn the new
``AssetResolution`` shape.

The public name :func:`locate_static_dir` now delegates to
:func:`asyncviz.packaging.assets.locate_frontend_bundle` so editable
and wheel installs share a single implementation across the codebase.
"""

from __future__ import annotations

from pathlib import Path

from asyncviz.packaging.assets import locate_frontend_bundle


def locate_static_dir() -> Path:
    """Return the canonical ``static`` directory inside the package.

    Thin wrapper over
    :func:`asyncviz.packaging.assets.locate_frontend_bundle` that
    returns just the directory — preserved as the legacy entry point
    for FastAPI mounting and the
    :data:`asyncviz.dashboard.app.STATIC_DIR` constant.
    """
    return locate_frontend_bundle().bundle_dir
