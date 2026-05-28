#!/usr/bin/env bash
# Terminate stale AsyncViz dev processes. Lists matches by default;
# pass --force to actually send SIGTERM.
. "$(dirname "$0")/../utils/lib.sh"

FORCE=0
for arg in "$@"; do
  case "$arg" in
    -f|--force) FORCE=1 ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/utils/kill-stale.sh [--force]

By default this script only lists matching processes. With --force it
sends SIGTERM to each matching PID.
USAGE
      exit 0
      ;;
  esac
done

PATTERNS=(
  "python.* -m asyncviz"
  "asyncviz/scripts/dev/start.py"
  "node .*vite"
)

found=0
for pattern in "${PATTERNS[@]}"; do
  # pgrep -f works on both macOS (BSD) and Linux.
  pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
  if [ -z "$pids" ]; then
    continue
  fi
  found=1
  while IFS= read -r pid; do
    # Skip our own pgrep / shell.
    [ "$pid" = "$$" ] && continue
    cmd="$(ps -o command= -p "$pid" 2>/dev/null || echo '<gone>')"
    if [ "$FORCE" -eq 1 ]; then
      warn "Killing ${pid}: ${cmd}"
      kill -TERM "$pid" 2>/dev/null || true
    else
      info "PID ${pid}: ${cmd}"
    fi
  done <<<"$pids"
done

if [ "$found" -eq 0 ]; then
  ok "No stale processes detected."
elif [ "$FORCE" -eq 0 ]; then
  info "Re-run with --force to terminate the processes above."
fi
