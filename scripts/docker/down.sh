#!/usr/bin/env bash
# Stop the AsyncViz stack (keeps volumes).
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
log "docker compose down"
compose down --remove-orphans "$@"
ok "Stack stopped."
