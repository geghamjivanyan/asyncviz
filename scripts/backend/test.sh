#!/usr/bin/env bash
# Run the backend test suite. Extra args pass through to pytest.
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
PYTHON="$(detect_python)"
exec "${PYTHON}" -m pytest "$@"
