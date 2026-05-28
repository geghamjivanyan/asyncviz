#!/usr/bin/env bash
# Auto-format the Python codebase (ruff format + ruff --fix).
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
PYTHON="$(detect_python)"
log "ruff format"
"${PYTHON}" -m ruff format .
log "ruff check --fix"
"${PYTHON}" -m ruff check --fix .
ok "Backend formatted."
