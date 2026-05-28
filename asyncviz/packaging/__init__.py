"""Canonical production-packaging surface for AsyncViz.

Everything here is import-time cheap so the embedded server can pull
``PackageMetadata`` / ``locate_frontend_bundle`` without dragging in
test or build dependencies.

The module owns five concerns:

* **Asset resolution** (:mod:`assets`) — locate the embedded frontend
  bundle on disk, whether the package was installed from a wheel, an
  sdist, an editable install, or a zipapp.
* **Versioning** (:mod:`versioning`) — single source of truth for the
  package version and build metadata (timestamp, git ref, frontend
  build manifest).
* **Build metadata** (:mod:`build_metadata`) — a typed, dataclass-only
  view of the embedded-bundle's build manifest, suitable for the
  diagnostics endpoint and the CLI.
* **Wheel validation** (:mod:`wheel_validation`) — inspect a wheel /
  sdist artifact and report whether the embedded bundle is present
  and well-formed.
* **Diagnostics** (:mod:`diagnostics`) — runtime self-report consumed
  by the diagnostics endpoint.

Other layers (the FastAPI app, the CLI, scripts) import from this
package rather than reaching into the implementation modules.
"""

from asyncviz.packaging.assets import (
    AssetResolution,
    EditableInstall,
    InstallShape,
    PackagedInstall,
    UnknownInstall,
    bundle_files,
    locate_frontend_bundle,
    resolve_frontend_asset,
)
from asyncviz.packaging.build_metadata import (
    BundleManifest,
    BundleManifestEntry,
    load_bundle_manifest,
)
from asyncviz.packaging.diagnostics import (
    PackagingDiagnostics,
    build_packaging_diagnostics,
)
from asyncviz.packaging.versioning import (
    BuildIdentity,
    PackageMetadata,
    get_package_metadata,
    package_version,
)
from asyncviz.packaging.wheel_validation import (
    WheelValidationIssue,
    WheelValidationReport,
    validate_sdist,
    validate_wheel,
)

__all__ = [
    "AssetResolution",
    "BuildIdentity",
    "BundleManifest",
    "BundleManifestEntry",
    "EditableInstall",
    "InstallShape",
    "PackageMetadata",
    "PackagedInstall",
    "PackagingDiagnostics",
    "UnknownInstall",
    "WheelValidationIssue",
    "WheelValidationReport",
    "build_packaging_diagnostics",
    "bundle_files",
    "get_package_metadata",
    "load_bundle_manifest",
    "locate_frontend_bundle",
    "package_version",
    "resolve_frontend_asset",
    "validate_sdist",
    "validate_wheel",
]
