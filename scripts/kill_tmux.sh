#!/usr/bin/env bash
set -euo pipefail

# Configuration from environment or defaults
SOCKET="${POLI_TMUX_SOCKET:-poli}"
SESSION="${POLI_TMUX_SESSION:-main}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Killing PoliTerm tmux session...${NC}"

# Check if session exists
if tmux -L "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    # Kill the session
    tmux -L "$SOCKET" kill-session -t "$SESSION"
    echo -e "${GREEN}✓ Session '$SESSION' on socket '$SOCKET' has been terminated${NC}"
else
    echo -e "${YELLOW}Session '$SESSION' on socket '$SOCKET' does not exist${NC}"
fi

# Also try to kill the server for this socket (cleanup)
if tmux -L "$SOCKET" list-sessions 2>/dev/null | grep -q .; then
    echo "Other sessions still exist on socket '$SOCKET'"
else
    # No more sessions, kill the server
    tmux -L "$SOCKET" kill-server 2>/dev/null || true
    echo -e "${GREEN}✓ tmux server for socket '$SOCKET' has been terminated${NC}"
fi