#!/usr/bin/env bash
# Start the AsyncViz stack in detached mode.
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
log "docker compose up -d"
compose up -d "$@"
ok "Backend: http://localhost:8877  •  Frontend: http://localhost:5173"
info "Tail logs with: make docker-logs"
