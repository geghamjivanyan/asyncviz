#!/usr/bin/env bash
# Run the AsyncViz backend (python -m asyncviz).
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
PYTHON="$(detect_python)"
exec "${PYTHON}" -m asyncviz "$@"
