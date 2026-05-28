#!/usr/bin/env bash
# Lint + format check the Python codebase.
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
PYTHON="$(detect_python)"
log "ruff check"
"${PYTHON}" -m ruff check .
log "ruff format --check"
"${PYTHON}" -m ruff format --check .
ok "Backend lint passed."
