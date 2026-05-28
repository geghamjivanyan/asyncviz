#!/usr/bin/env python3
"""End-to-end dashboard-bundle smoke check.

Boots the embedded FastAPI dashboard against the current install
(editable or wheel-installed) and confirms the SPA index.html is
served + the asset diagnostics endpoint reports a healthy bundle.

Usage:

    python scripts/packaging/verify_dashboard_bundle.py
    python scripts/packaging/verify_dashboard_bundle.py --json
"""

from __future__ import annotations

import argparse
import json
import sys

from fastapi.testclient import TestClient

from asyncviz.dashboard import create_app


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test the embedded dashboard bundle.")
    parser.add_argument("--json", dest="emit_json", action="store_true")
    args = parser.parse_args()

    app = create_app()
    with TestClient(app) as client:
        index = client.get("/")
        assets = client.get("/api/assets")
        packaging = client.get("/api/packaging")

    payload = {
        "index_status": index.status_code,
        "index_bytes": len(index.content),
        "assets_status": assets.status_code,
        "assets_payload": assets.json() if assets.status_code == 200 else None,
        "packaging_status": packaging.status_code,
        "packaging_payload": packaging.json() if packaging.status_code == 200 else None,
    }

    if args.emit_json:
        json.dump(payload, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        print(f"GET /            -> {index.status_code} ({len(index.content)} bytes)", flush=True)
        print(f"GET /api/assets  -> {assets.status_code}", flush=True)
        if assets.status_code == 200:
            body = assets.json()
            validation = body.get("validation", {})
            print(
                f"  bundle.is_published={body['bundle']['is_published']} "
                f"validation.ok={validation.get('ok')} "
                f"files={validation.get('file_count')}",
                flush=True,
            )
        print(f"GET /api/packaging -> {packaging.status_code}", flush=True)

    ok = (
        index.status_code == 200
        and assets.status_code == 200
        and assets.json().get("validation", {}).get("ok") is True
        and packaging.status_code == 200
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
