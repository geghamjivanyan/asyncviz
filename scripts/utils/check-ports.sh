#!/usr/bin/env bash
# Report whether AsyncViz dev ports are in use.
. "$(dirname "$0")/../utils/lib.sh"

PORTS=("${@:-8877 5173}")

check_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pid
    pid="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    if [ -n "$pid" ]; then
      warn "Port ${port} is in use by PID(s): ${pid}"
      return 1
    fi
  else
    warn "lsof not available; cannot inspect port ${port}"
    return 0
  fi
  ok "Port ${port} is free."
  return 0
}

status=0
# shellcheck disable=SC2068
for p in ${PORTS[@]}; do
  check_port "$p" || status=1
done
exit "$status"
