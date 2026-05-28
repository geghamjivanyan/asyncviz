#!/usr/bin/env bash
# Start backend + frontend together via the Python orchestrator.
. "$(dirname "$0")/../utils/lib.sh"
PYTHON="$(detect_python)"
exec "${PYTHON}" "${REPO_ROOT}/scripts/dev/start.py" "$@"
