#!/usr/bin/env bash
# Remove cache and build artifacts. Preserves .venv and node_modules.
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
log "Removing caches and build outputs"
rm -rf .ruff_cache .pytest_cache .coverage coverage.xml htmlcov build dist
rm -rf frontend/dist frontend/.vite
find . -type d -name __pycache__ -prune -exec rm -rf {} +
ok "Workspace cleaned."
