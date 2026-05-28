from __future__ import annotations

from fastapi.testclient import TestClient

from asyncviz.dashboard import create_app
from asyncviz.packaging import (
    build_packaging_diagnostics,
    get_package_metadata,
    package_version,
)


def test_build_packaging_diagnostics_uses_metadata() -> None:
    meta = get_package_metadata()
    diag = build_packaging_diagnostics(meta)
    assert diag.version == meta.version
    assert diag.is_editable == meta.is_editable
    assert diag.bundle_dir == str(meta.asset_resolution.bundle_dir)
    assert diag.install_shape == meta.asset_resolution.install_shape.kind


def test_build_packaging_diagnostics_default_works() -> None:
    diag = build_packaging_diagnostics()
    assert diag.version == package_version()
    # to_dict() must be JSON-serializable.
    payload = diag.to_dict()
    assert set(payload.keys()) >= {
        "version",
        "channel",
        "is_editable",
        "bundle_present",
        "bundle_dir",
        "install_shape",
        "resolved_via",
        "bundle_file_count",
        "bundle_total_bytes",
        "manifest_source",
    }


def test_packaging_route_returns_diagnostics() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/api/packaging")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == package_version()
    assert body["install_shape"] in {"editable", "packaged", "unknown"}
    assert isinstance(body["bundle_file_count"], int)
    assert isinstance(body["missing_files"], list)


def test_packaging_route_in_openapi_schema() -> None:
    app = create_app()
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()
    assert "/api/packaging" in schema["paths"], schema["paths"].keys()
