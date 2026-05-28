#!/usr/bin/env bash
# Open a shell (or run a command) inside a running service container.
# Usage: scripts/docker/exec.sh [service] [command...]
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
service="${1:-backend}"
shift || true
if [ "$#" -eq 0 ]; then
  set -- /bin/sh
fi
exec_cmd=(exec "$service" "$@")
compose "${exec_cmd[@]}"
