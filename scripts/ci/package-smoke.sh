#!/usr/bin/env bash
# Build the wheel, install it in a fresh venv, and verify that the embedded
# frontend ships inside the package and the dashboard server can find it.
. "$(dirname "$0")/../utils/lib.sh"

cd "${REPO_ROOT}"
require_cmd python3

WORKDIR="$(mktemp -d /tmp/asyncviz-package-smoke.XXXXXX)"
trap 'rm -rf "${WORKDIR}"' EXIT

log "Embedding frontend"
"${REPO_ROOT}/scripts/frontend/build-prod.sh"

log "Building Python wheel into ${WORKDIR}/dist"
PYTHON="$(detect_python)"
"${PYTHON}" -m pip install --quiet --upgrade build
"${PYTHON}" -m build --wheel --outdir "${WORKDIR}/dist" >"${WORKDIR}/build.log" 2>&1 || {
  err "wheel build failed; tail of log:"
  tail -20 "${WORKDIR}/build.log" >&2
  exit 1
}

wheel="$(find "${WORKDIR}/dist" -name '*.whl' -maxdepth 1 -print -quit)"
[ -n "${wheel}" ] || { err "no wheel produced"; exit 1; }

log "Inspecting wheel contents"
"${PYTHON}" -m zipfile -l "${wheel}" | grep 'asyncviz/dashboard/static' >"${WORKDIR}/wheel-contents.txt" || {
  err "wheel does not include asyncviz/dashboard/static/*"
  exit 1
}
ok "Wheel contains $(wc -l <"${WORKDIR}/wheel-contents.txt" | tr -d ' ') embedded frontend entries"

log "Installing wheel into a fresh venv"
python3 -m venv "${WORKDIR}/venv"
"${WORKDIR}/venv/bin/pip" install --quiet --upgrade pip
"${WORKDIR}/venv/bin/pip" install --quiet "${wheel}"

log "Verifying embedded frontend resolves from the installed package"
cd "${WORKDIR}" && "${WORKDIR}/venv/bin/python" - <<'PY'
from pathlib import Path

import asyncviz
import asyncviz.dashboard.app as app_mod

static = app_mod.STATIC_DIR
index = static / "index.html"
assets = static / "assets"

assert "site-packages" in str(static), f"package not installed: {static}"
assert index.is_file(), f"missing {index}"
assert assets.is_dir(), f"missing {assets}"

asset_files = [p for p in assets.iterdir() if p.is_file()]
assert asset_files, f"no asset files in {assets}"

print(f"asyncviz {asyncviz.__version__}")
print(f"static : {static}")
print(f"index  : {index}")
print(f"assets : {len(asset_files)} files")
PY

log "Verifying the dashboard server starts and serves index.html"
cd "${WORKDIR}" && "${WORKDIR}/venv/bin/python" - <<'PY'
import urllib.request

import asyncviz

asyncviz.start(host="127.0.0.1", port=8931, open_browser=False)
try:
    with urllib.request.urlopen("http://127.0.0.1:8931/", timeout=3) as r:
        body = r.read().decode()
    assert r.status == 200
    assert "<html" in body.lower(), f"unexpected body: {body[:200]!r}"
    print("served:", len(body), "bytes")
finally:
    asyncviz.stop()
PY

ok "Wheel install smoke passed."
