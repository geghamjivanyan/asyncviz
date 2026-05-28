#!/usr/bin/env bash
# Build all AsyncViz containers (dev targets by default).
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
log "docker compose build"
compose build "$@"
ok "Build complete."
