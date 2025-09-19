#!/usr/bin/env bash
set -euo pipefail

# Configuration from environment or defaults
SOCKET="${POLI_TMUX_SOCKET:-poli}"

if [[ -n "${POLI_TMUX_SESSIONS:-}" ]]; then
  SESSION_LIST="${POLI_TMUX_SESSIONS}"
elif [[ -n "${POLI_TMUX_SESSION:-}" ]]; then
  SESSION_LIST="${POLI_TMUX_SESSION}"
else
  SESSION_LIST="main planner executer"
fi

IFS=' ' read -r -a RAW_SESSIONS <<< "${SESSION_LIST//,/ }"
SESSIONS=()
for sess in "${RAW_SESSIONS[@]}"; do
  if [[ -n "$sess" ]]; then
    SESSIONS+=("$sess")
  fi
done

if [[ ${#SESSIONS[@]} -eq 0 ]]; then
  SESSIONS=("main")
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Killing PoliTerm tmux sessions on socket '$SOCKET'...${NC}"

for SESSION in "${SESSIONS[@]}"; do
  if tmux -L "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    tmux -L "$SOCKET" kill-session -t "$SESSION"
    echo -e "${GREEN}✓ Session '$SESSION' terminated${NC}"
  else
    echo -e "${YELLOW}Session '$SESSION' not found${NC}"
  fi
done

if tmux -L "$SOCKET" list-sessions 2>/dev/null | grep -q .; then
  echo -e "${YELLOW}Other tmux sessions remain on socket '$SOCKET'; server left running${NC}"
else
  tmux -L "$SOCKET" kill-server 2>/dev/null || true
  echo -e "${GREEN}✓ tmux server for socket '$SOCKET' has been terminated${NC}"
fi
