from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from asyncviz.config import AsyncVizConfig
from asyncviz.dashboard import create_app
from asyncviz.dashboard.frontend_serving import (
    CACHE_IMMUTABLE,
    CACHE_NO_CACHE,
    CACHE_SHORT,
    FRONTEND_PROTOCOL_VERSION,
    RESERVED_PREFIXES,
    AssetResolver,
    CachePolicy,
    FrontendServingConfig,
    FrontendServingMetrics,
    FrontendServingService,
    PathTraversalRejectedError,
    discover_manifest,
    header_for,
    is_reserved_path,
    load_manifest,
    locate_static_dir,
)
from asyncviz.dashboard.frontend_serving.exceptions import ManifestLoadError

# ── Shared fixtures ───────────────────────────────────────────────────────


def _build_bundle(tmp_path: Path) -> Path:
    """Materialize a fake Vite bundle at ``tmp_path`` and return the path."""
    (tmp_path / "index.html").write_text(
        '<!doctype html><title>asyncviz</title><script src="/assets/index-abc123.js"></script>'
    )
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "index-abc123.js").write_text("console.log('hello');\n")
    (assets / "index-abc123.css").write_text("body{background:#000;}\n")
    (tmp_path / "favicon.ico").write_bytes(b"\x00\x00")
    (tmp_path / "robots.txt").write_text("User-agent: *\nDisallow:\n")
    return tmp_path


# ── Cache primitives ──────────────────────────────────────────────────────


def test_cache_header_for_each_policy() -> None:
    assert header_for(CachePolicy.IMMUTABLE) == CACHE_IMMUTABLE
    assert header_for(CachePolicy.SHORT) == CACHE_SHORT
    assert header_for(CachePolicy.NO_CACHE) == CACHE_NO_CACHE


def test_cache_constants_match_protocol() -> None:
    # The wire shape is part of the public protocol — guard against drift.
    assert CACHE_IMMUTABLE == "public, max-age=31536000, immutable"
    assert CACHE_SHORT == "public, max-age=3600"
    assert CACHE_NO_CACHE == "no-cache"


# ── SPA predicate ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path,reserved",
    [
        # Catch-all form (no leading slash) — what FastAPI's
        # ``{full_path:path}`` hands the SPA handler.
        ("api/health", True),
        ("api/runtime/snapshot", True),
        ("api", True),
        ("ws", True),
        ("openapi.json", True),
        ("docs", True),
        ("docs/oauth2-redirect", True),
        ("redoc", True),
        ("health", True),
        ("health/live", True),
        ("health/ready", True),
        ("health/runtime", True),
        # Raw request form (with leading slash) — what ASGI scope
        # exposes. Both forms must produce the same verdict.
        ("/api/health", True),
        ("/health", True),
        ("/health/live", True),
        ("/docs", True),
        ("/openapi.json", True),
        ("/ws", True),
        # Genuine SPA routes — must not be intercepted.
        ("", False),
        ("/", False),
        ("index.html", False),
        ("timeline", False),
        ("metrics", False),
        ("warnings", False),
        ("replay", False),
        ("diagnostics", False),
        ("tasks/123", False),
        ("assets/index-abc.js", False),
        # Boundary cases — paths that *start with* a reserved word
        # but live on their own top-level route, not as a child of a
        # reserved prefix. These must fall through to the SPA.
        ("api-docs", False),
        ("apiary", False),
        ("/api-docs", False),
        ("health-check-overview", False),
        ("healthz-but-not-ours", False),
        ("/healthz", False),
        ("websocket-debugger", False),
    ],
)
def test_is_reserved_path(path: str, reserved: bool) -> None:
    assert is_reserved_path(path) is reserved


def test_reserved_prefixes_are_canonical_leading_slash_strings() -> None:
    # Canonical wire form: leading slash, no trailing slash. This is
    # the format operators type into curl + browsers and is the form
    # documented in the routing-contract module docstring.
    assert isinstance(RESERVED_PREFIXES, tuple)
    assert all(isinstance(p, str) for p in RESERVED_PREFIXES)
    assert all(p.startswith("/") for p in RESERVED_PREFIXES)
    assert all(not p.endswith("/") for p in RESERVED_PREFIXES)


def test_reserved_prefixes_cover_all_backend_surfaces() -> None:
    # If a new backend mount lands without an entry here, the SPA
    # catch-all will silently shadow it (returning index.html with 200
    # — the exact bug this module exists to prevent). Lock the set so
    # an additive change becomes an explicit test update.
    assert set(RESERVED_PREFIXES) == {
        "/api",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/ws",
    }


# ── Packaging ────────────────────────────────────────────────────────────


def test_locate_static_dir_resolves_inside_package() -> None:
    static = locate_static_dir()
    assert static.name == "static"
    # The dashboard package owns it.
    assert static.parent.name == "dashboard"


# ── AssetResolver ─────────────────────────────────────────────────────────


def test_resolver_finds_existing_asset(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    resolver = AssetResolver(tmp_path)
    asset = resolver.resolve("assets/index-abc123.js")
    assert asset is not None
    assert asset.policy is CachePolicy.IMMUTABLE
    assert asset.relative == "assets/index-abc123.js"
    assert asset.path.is_file()


def test_resolver_resolves_index_on_empty_path(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    resolver = AssetResolver(tmp_path)
    asset = resolver.resolve("")
    assert asset is not None
    assert asset.relative == "index.html"
    assert asset.policy is CachePolicy.NO_CACHE


def test_resolver_classifies_loose_asset_with_short_cache(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    resolver = AssetResolver(tmp_path)
    asset = resolver.resolve("favicon.ico")
    assert asset is not None
    assert asset.policy is CachePolicy.SHORT


def test_resolver_classifies_index_with_no_cache(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    resolver = AssetResolver(tmp_path)
    asset = resolver.resolve("index.html")
    assert asset is not None
    assert asset.policy is CachePolicy.NO_CACHE


def test_resolver_misses_unknown_file(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    resolver = AssetResolver(tmp_path)
    assert resolver.resolve("does-not-exist.txt") is None


def test_resolver_rejects_path_traversal(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    _build_bundle(bundle)
    # Material outside the bundle that an attacker would try to reach.
    (tmp_path / "secret.txt").write_text("ssh keys here")

    resolver = AssetResolver(bundle)
    with pytest.raises(PathTraversalRejectedError):
        resolver.resolve("../secret.txt")


def test_resolver_counts_and_sizes_assets(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    resolver = AssetResolver(tmp_path)
    assert resolver.asset_count() == 2
    assert resolver.asset_size_bytes() > 0
    names = resolver.asset_names()
    assert names == sorted(names)
    assert names == ["index-abc123.css", "index-abc123.js"]


def test_resolver_reports_no_bundle(tmp_path: Path) -> None:
    resolver = AssetResolver(tmp_path)
    assert resolver.has_bundle() is False
    assert resolver.has_assets_dir() is False
    assert resolver.asset_count() == 0
    assert resolver.asset_size_bytes() == 0
    assert resolver.asset_names() == []


# ── Manifest discovery ────────────────────────────────────────────────────


def test_discover_manifest_synthesizes_from_filesystem(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    manifest = discover_manifest(tmp_path, tmp_path / "assets")
    assert manifest.source == "scan"
    assert not manifest.is_empty
    assert manifest.entry is not None
    assert manifest.entry.file == "assets/index-abc123.js"
    assert manifest.entry.is_entry is True
    # Both files surface in the manifest.
    files = {e.file for e in manifest.entries}
    assert files == {"assets/index-abc123.js", "assets/index-abc123.css"}


def test_discover_manifest_returns_missing_for_no_assets(tmp_path: Path) -> None:
    manifest = discover_manifest(tmp_path, tmp_path / "assets")
    assert manifest.source == "missing"
    assert manifest.is_empty
    assert manifest.entry is None


def test_load_manifest_parses_vite_format(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    manifest_dir = tmp_path / ".vite"
    manifest_dir.mkdir()
    manifest_data = {
        "src/main.tsx": {
            "file": "assets/index-abc123.js",
            "isEntry": True,
            "css": ["assets/index-abc123.css"],
        },
    }
    manifest_path = manifest_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data))

    manifest = load_manifest(manifest_path, static_dir=tmp_path)
    assert manifest.source == "vite"
    assert manifest.entry is not None
    assert manifest.entry.file == "assets/index-abc123.js"
    assert manifest.entry.css == ("assets/index-abc123.css",)


def test_load_manifest_raises_on_invalid_json(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{ this is not json")
    with pytest.raises(ManifestLoadError):
        load_manifest(manifest_path, static_dir=tmp_path)


def test_load_manifest_raises_on_non_object_root(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(["this", "is", "an", "array"]))
    with pytest.raises(ManifestLoadError):
        load_manifest(manifest_path, static_dir=tmp_path)


# ── FrontendServingMetrics ────────────────────────────────────────────────


def test_metrics_counts_each_outcome() -> None:
    metrics = FrontendServingMetrics()
    metrics.record_asset_request()
    metrics.record_immutable_hit()
    metrics.record_loose_hit()
    metrics.record_index_served()
    metrics.record_spa_fallback()
    metrics.record_reserved_blocked()
    metrics.record_path_traversal_blocked()
    metrics.record_manifest_load()
    metrics.record_manifest_load(failed=True)
    metrics.record_asset_miss()
    snap = metrics.snapshot()
    assert snap.asset_requests == 1
    assert snap.asset_hits == 2  # immutable + loose
    assert snap.immutable_hits == 1
    assert snap.loose_hits == 1
    assert snap.asset_misses == 1
    assert snap.index_served == 1
    assert snap.spa_fallbacks == 1
    assert snap.reserved_blocked == 1
    assert snap.path_traversal_blocked == 1
    assert snap.manifest_loads == 1
    assert snap.manifest_load_failures == 1


def test_metrics_reset_clears() -> None:
    metrics = FrontendServingMetrics()
    metrics.record_index_served()
    metrics.reset()
    assert metrics.snapshot().index_served == 0


# ── FrontendServingService routing ────────────────────────────────────────


def _service_for(tmp_path: Path, *, mode="auto") -> FrontendServingService:
    _build_bundle(tmp_path)
    return FrontendServingService(FrontendServingConfig(static_dir=tmp_path, mode=mode))


def test_service_should_mount_auto_when_bundle_present(tmp_path: Path) -> None:
    svc = _service_for(tmp_path, mode="auto")
    assert svc.should_mount() is True


def test_service_should_not_mount_auto_when_bundle_missing(tmp_path: Path) -> None:
    svc = FrontendServingService(FrontendServingConfig(static_dir=tmp_path, mode="auto"))
    assert svc.should_mount() is False


def test_service_api_only_never_mounts(tmp_path: Path) -> None:
    svc = _service_for(tmp_path, mode="api-only")
    assert svc.should_mount() is False


def test_service_embedded_always_mounts(tmp_path: Path) -> None:
    # Even with no bundle on disk, embedded mode says "mount" — the
    # bootstrap validation is responsible for pre-flighting the bundle.
    svc = FrontendServingService(FrontendServingConfig(static_dir=tmp_path, mode="embedded"))
    assert svc.should_mount() is True


def test_service_mount_is_idempotent(tmp_path: Path) -> None:
    svc = _service_for(tmp_path)
    app = FastAPI()
    svc.mount(app)
    assert svc.is_mounted is True
    # Second call is a no-op (no duplicate routes).
    svc.mount(app)


def test_service_serves_spa_index_at_root(tmp_path: Path) -> None:
    svc = _service_for(tmp_path)
    app = FastAPI()
    svc.mount(app)
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "asyncviz" in response.text
    assert response.headers["cache-control"] == CACHE_NO_CACHE


def test_service_falls_back_to_index_for_deep_routes(tmp_path: Path) -> None:
    svc = _service_for(tmp_path)
    app = FastAPI()
    svc.mount(app)
    with TestClient(app) as client:
        response = client.get("/some/deep/route")
    assert response.status_code == 200
    assert "asyncviz" in response.text
    snap = svc.metrics_snapshot()
    assert snap.spa_fallbacks >= 1
    assert snap.index_served >= 1


def test_service_blocks_reserved_prefixes(tmp_path: Path) -> None:
    svc = _service_for(tmp_path)
    # Call directly into ``serve_path`` so we exercise the reserved-prefix
    # branch in isolation — FastAPI's own ``/openapi.json`` route would
    # otherwise intercept some of these on a bare app.
    from fastapi import HTTPException

    reserved = (
        "api/anything",
        "api",
        "ws",
        "openapi.json",
        "docs",
        "redoc",
        # /health was the regression — make sure the catch-all 404s it
        # rather than serving the SPA shell.
        "health",
        "health/live",
        "health/ready",
    )
    for path in reserved:
        with pytest.raises(HTTPException) as info:
            svc.serve_path(path)
        assert info.value.status_code == 404
    snap = svc.metrics_snapshot()
    assert snap.reserved_blocked >= len(reserved)


def test_service_does_not_block_paths_resembling_reserved_prefixes(
    tmp_path: Path,
) -> None:
    # Regression guard for the boundary-respecting matcher: a frontend
    # route that happens to *start with* the same bytes as a reserved
    # prefix (``/api-docs``, ``/healthz``, ``/wsdebug``) must fall
    # through to the SPA, not 404.
    svc = _service_for(tmp_path)
    for path in ("api-docs", "apiary", "healthz", "health-check", "wsdebug"):
        # Should not raise — should resolve to either a real file or
        # the SPA index fallback.
        response = svc.serve_path(path)
        assert response.status_code == 200


def test_service_serves_immutable_assets_via_mount(tmp_path: Path) -> None:
    svc = _service_for(tmp_path)
    app = FastAPI()
    svc.mount(app)
    with TestClient(app) as client:
        response = client.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == CACHE_IMMUTABLE
    snap = svc.metrics_snapshot()
    assert snap.immutable_hits >= 1


def test_service_serves_loose_assets_with_short_cache(tmp_path: Path) -> None:
    svc = _service_for(tmp_path)
    app = FastAPI()
    svc.mount(app)
    with TestClient(app) as client:
        response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["cache-control"] == CACHE_SHORT


def test_service_records_path_traversal_block(tmp_path: Path) -> None:
    svc = _service_for(tmp_path)
    # Starlette typically normalizes ``..`` in the URL before our handler
    # runs, so we directly call into the service to assert the typed
    # rejection path. The catch-all uses the same code.
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as info:
        svc.serve_path("../../etc/passwd")
    assert info.value.status_code == 404
    assert svc.metrics_snapshot().path_traversal_blocked >= 1


def test_service_uses_vite_manifest_when_present(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    manifest_dir = tmp_path / ".vite"
    manifest_dir.mkdir()
    (manifest_dir / "manifest.json").write_text(
        json.dumps(
            {
                "src/main.tsx": {
                    "file": "assets/index-abc123.js",
                    "isEntry": True,
                    "css": ["assets/index-abc123.css"],
                }
            }
        )
    )
    svc = FrontendServingService(FrontendServingConfig(static_dir=tmp_path))
    assert svc.manifest.source == "vite"
    assert svc.metrics_snapshot().manifest_loads >= 1


def test_service_degrades_to_scan_on_broken_manifest(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    manifest_dir = tmp_path / ".vite"
    manifest_dir.mkdir()
    (manifest_dir / "manifest.json").write_text("not valid json")
    svc = FrontendServingService(FrontendServingConfig(static_dir=tmp_path))
    # The corrupt manifest is logged as a degradation; the service
    # falls back to a filesystem scan and stays operational.
    assert svc.manifest.source == "scan"
    assert svc.metrics_snapshot().manifest_load_failures >= 1


def test_service_reload_manifest_picks_up_new_assets(tmp_path: Path) -> None:
    _build_bundle(tmp_path)
    svc = FrontendServingService(FrontendServingConfig(static_dir=tmp_path))
    before = len(svc.manifest.entries)
    # Add a new asset, then reload.
    (tmp_path / "assets" / "vendor-zyx.js").write_text("/* vendor */")
    svc.reload_manifest()
    after = len(svc.manifest.entries)
    assert after == before + 1


# ── End-to-end through create_app ─────────────────────────────────────────


def test_api_only_mode_skips_mount() -> None:
    app = create_app(AsyncVizConfig(frontend_mode="api-only"))
    svc = app.state.frontend_serving
    # Even though the bundle exists in the embedded static dir, mode
    # forces a skip.
    assert svc.is_mounted is True  # mount() ran; mode said "don't add routes"
    with TestClient(app) as client:
        # SPA catch-all should not be registered; an unknown path is 404.
        response = client.get("/some/spa/route")
        # FastAPI returns 404 for unmatched routes in api-only mode.
        assert response.status_code == 404
        # API routes still work.
        assert client.get("/api/health/live").status_code == 200


def test_create_app_exposes_frontend_serving_on_backend_state() -> None:
    app = create_app(AsyncVizConfig(frontend_mode="api-only"))
    assert app.state.backend.frontend_serving is app.state.frontend_serving


def test_frontend_diagnostics_endpoint_shape() -> None:
    app = create_app(AsyncVizConfig(frontend_mode="auto"))
    with TestClient(app) as client:
        response = client.get("/api/runtime/frontend")
    assert response.status_code == 200
    data = response.json()
    assert data["protocol_version"] == FRONTEND_PROTOCOL_VERSION
    for key in (
        "mode",
        "static_dir",
        "bundle_present",
        "assets_dir_present",
        "asset_count",
        "asset_size_bytes",
        "entry_module",
        "entry_css",
        "manifest_source",
        "manifest_entries",
    ):
        assert key in data


def test_frontend_diagnostics_reflects_api_only_mode() -> None:
    app = create_app(AsyncVizConfig(frontend_mode="api-only"))
    with TestClient(app) as client:
        data = client.get("/api/runtime/frontend").json()
    assert data["mode"] == "api-only"
    # In api-only mode the bundle might still exist on disk — we just
    # don't mount it. The endpoint should report the actual state.
    assert "bundle_present" in data


def test_frontend_metrics_endpoint_counts_traffic() -> None:
    app = create_app(AsyncVizConfig(frontend_mode="auto"))
    with TestClient(app) as client:
        client.get("/some/spa/route")
        client.get("/some/other/route")
        data = client.get("/api/runtime/frontend/metrics").json()
    # We hit the SPA fallback twice in this run.
    assert data["spa_fallbacks"] >= 2
    assert data["index_served"] >= 2
