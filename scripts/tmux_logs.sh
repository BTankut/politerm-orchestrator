#!/usr/bin/env bash
set -euo pipefail

# Enable/disable raw tmux pane logging for planner/executer
# Usage:
#   ./scripts/tmux_logs.sh on
#   ./scripts/tmux_logs.sh off

SOCKET="${POLI_TMUX_SOCKET:-poli}"
PLANNER_TARGET="${POLI_PLANNER_TARGET:-${POLI_TMUX_PLANNER_SESSION:-planner}:tui.0}"
EXECUTER_TARGET="${POLI_EXECUTER_TARGET:-${POLI_TMUX_EXECUTER_SESSION:-executer}:tui.0}"
LOG_DIR="${POLI_LOG_DIR:-logs}"
mkdir -p "$LOG_DIR"

cmd=${1:-}
if [[ "$cmd" != "on" && "$cmd" != "off" ]]; then
  echo "Usage: $0 on|off" >&2
  exit 1
fi

if [[ "$cmd" == "on" ]]; then
  tmux -L "$SOCKET" pipe-pane -o -t "$PLANNER_TARGET" "ts >> $LOG_DIR/planner_pane.log"
  tmux -L "$SOCKET" pipe-pane -o -t "$EXECUTER_TARGET" "ts >> $LOG_DIR/executer_pane.log"
  echo "tmux pane logging enabled -> $LOG_DIR/{planner_pane.log,executer_pane.log}"
else
  tmux -L "$SOCKET" pipe-pane -t "$PLANNER_TARGET"
  tmux -L "$SOCKET" pipe-pane -t "$EXECUTER_TARGET"
  echo "tmux pane logging disabled"
fi

