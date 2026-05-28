#!/usr/bin/env bash
# Follow logs from all services (or a specific one if a name is passed).
. "$(dirname "$0")/../utils/lib.sh"
cd "${REPO_ROOT}"
exec_args=(logs --follow --tail=200)
if [ "$#" -gt 0 ]; then
  exec_args+=("$@")
fi
compose "${exec_args[@]}"
