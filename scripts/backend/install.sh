#!/usr/bin/env bash
# Create .venv (if missing) and install backend in editable mode with dev extras.
. "$(dirname "$0")/../utils/lib.sh"

cd "${REPO_ROOT}"

PYTHON_BOOT="${ASYNCVIZ_PYTHON:-python3}"
require_cmd "${PYTHON_BOOT}"

if [ ! -d .venv ]; then
  log "Creating virtualenv at .venv"
  "${PYTHON_BOOT}" -m venv .venv
else
  info "Reusing existing .venv"
fi

VENV_PIP="${REPO_ROOT}/.venv/bin/pip"
log "Upgrading pip"
"${VENV_PIP}" install --quiet --upgrade pip

log "Installing asyncviz[dev]"
"${VENV_PIP}" install --quiet -e ".[dev]"

ok "Backend installed."
