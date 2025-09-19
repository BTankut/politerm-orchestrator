#!/usr/bin/env bash
set -euo pipefail

# Resolve repository root relative to this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Determine python executables
DEFAULT_WIZ_PY="/opt/homebrew/bin/python3.9"
if [[ -n "${POLI_WIZARD_PYTHON:-}" ]]; then
  WIZARD_PYTHON="${POLI_WIZARD_PYTHON}"
elif command -v "$DEFAULT_WIZ_PY" >/dev/null 2>&1; then
  WIZARD_PYTHON="$DEFAULT_WIZ_PY"
else
  WIZARD_PYTHON="python3"
fi

if [[ -n "${POLI_ORCHESTRATOR_PYTHON:-}" ]]; then
  ORCH_PYTHON="${POLI_ORCHESTRATOR_PYTHON}"
else
  ORCH_PYTHON="python3"
fi

WIZARD_PATH="$REPO_ROOT/proto/poli_session_wizard.py"
ORCH_PATH="$REPO_ROOT/proto/poli_orchestrator_v3.py"

if [[ ! -f "$WIZARD_PATH" ]]; then
  echo "Wizard script not found at $WIZARD_PATH" >&2
  exit 1
fi

if [[ ! -f "$ORCH_PATH" ]]; then
  echo "Orchestrator script not found at $ORCH_PATH" >&2
  exit 1
fi

printf '>>> Launching PoliTerm wizard using %s\n' "$WIZARD_PYTHON"
if ! "$WIZARD_PYTHON" "$WIZARD_PATH" "$@"; then
  echo "Wizard exited with non-zero status. Aborting orchestrator startup." >&2
  exit 1
fi

printf '\n>>> Wizard finished. Starting orchestrator monitor using %s\n' "$ORCH_PYTHON"

start_orchestrator_current_shell() {
  cd "$REPO_ROOT"
  "$ORCH_PYTHON" "$ORCH_PATH" --monitor
}

if [[ "$OSTYPE" == darwin* ]] && command -v osascript >/dev/null 2>&1; then
  APPLE_SCRIPT=$(cat <<OSA
set repoPath to "$REPO_ROOT"
set orchCmd to "$ORCH_PYTHON $ORCH_PATH --monitor"

tell application "Terminal"
  do script "cd " & quoted form of repoPath & " && " & orchCmd
  activate
end tell
OSA
  )
  if osascript -e "$APPLE_SCRIPT" >/dev/null; then
    echo "Orchestrator started in a new Terminal window."
    exit 0
  else
    echo "Failed to open new Terminal window. Falling back to current shell." >&2
    start_orchestrator_current_shell
  fi
else
  echo "Running orchestrator in current shell (Ctrl+C to stop)."
  start_orchestrator_current_shell
fi
