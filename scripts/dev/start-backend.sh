#!/usr/bin/env bash
# Start only the backend dev server.
. "$(dirname "$0")/../utils/lib.sh"
PYTHON="$(detect_python)"
exec "${PYTHON}" "${REPO_ROOT}/scripts/dev/start.py" --backend-only "$@"
