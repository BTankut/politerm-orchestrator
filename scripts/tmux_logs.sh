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
  if command -v ts >/dev/null 2>&1; then
    CMD_P="ts >> $LOG_DIR/planner_pane.log"
    CMD_E="ts >> $LOG_DIR/executer_pane.log"
  else
    CMD_P=">> $LOG_DIR/planner_pane.log cat"
    CMD_E=">> $LOG_DIR/executer_pane.log cat"
  fi
  tmux -L "$SOCKET" pipe-pane -o -t "$PLANNER_TARGET" "$CMD_P"
  tmux -L "$SOCKET" pipe-pane -o -t "$EXECUTER_TARGET" "$CMD_E"
  echo "tmux pane logging enabled -> $LOG_DIR/{planner_pane.log,executer_pane.log}"
else
  tmux -L "$SOCKET" pipe-pane -t "$PLANNER_TARGET"
  tmux -L "$SOCKET" pipe-pane -t "$EXECUTER_TARGET"
  echo "tmux pane logging disabled"
fi
