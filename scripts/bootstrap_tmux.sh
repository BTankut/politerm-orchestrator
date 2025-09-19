#!/usr/bin/env bash
set -euo pipefail

# Configuration from environment or defaults
SOCKET="${POLI_TMUX_SOCKET:-poli}"
SESSION="${POLI_TMUX_SESSION:-main}"

PLANNER_CWD="${PLANNER_CWD:-$HOME/Workspace/ProjA}"
EXECUTER_CWD="${EXECUTER_CWD:-$HOME/Workspace/ProjB}"
PLANNER_CMD="${PLANNER_CMD:-claude}"
EXECUTER_CMD="${EXECUTER_CMD:-codex}"

# Paths to primer files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/../config"
if [ -f "$CONFIG_DIR/planner_primer_v3.txt" ]; then
    PLANNER_PRIMER_FILE="$CONFIG_DIR/planner_primer_v3.txt"
elif [ -f "$CONFIG_DIR/planner_primer_v2.txt" ]; then
    PLANNER_PRIMER_FILE="$CONFIG_DIR/planner_primer_v2.txt"
else
    PLANNER_PRIMER_FILE="$CONFIG_DIR/planner_primer.txt"
fi

if [ -f "$CONFIG_DIR/executer_primer_v3.txt" ]; then
    EXECUTER_PRIMER_FILE="$CONFIG_DIR/executer_primer_v3.txt"
elif [ -f "$CONFIG_DIR/executer_primer_v2.txt" ]; then
    EXECUTER_PRIMER_FILE="$CONFIG_DIR/executer_primer_v2.txt"
else
    EXECUTER_PRIMER_FILE="$CONFIG_DIR/executer_primer.txt"
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting PoliTerm Orchestrator tmux session...${NC}"

# Check if session already exists
if tmux -L "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    echo -e "${YELLOW}Warning: Session '$SESSION' already exists on socket '$SOCKET'${NC}"
    echo "Kill it first with: bash scripts/kill_tmux.sh"
    exit 1
fi

# Create working directories if they don't exist
if [ ! -d "$PLANNER_CWD" ]; then
    echo -e "${YELLOW}Creating PLANNER working directory: $PLANNER_CWD${NC}"
    mkdir -p "$PLANNER_CWD"
fi

if [ ! -d "$EXECUTER_CWD" ]; then
    echo -e "${YELLOW}Creating EXECUTER working directory: $EXECUTER_CWD${NC}"
    mkdir -p "$EXECUTER_CWD"
fi

# Create new tmux session with custom socket
echo "Creating tmux session '$SESSION' on socket '$SOCKET'..."
tmux -L "$SOCKET" -f /dev/null new-session -d -s "$SESSION" -c "$PLANNER_CWD"

# Start PLANNER in pane 0
echo "Starting PLANNER ($PLANNER_CMD) in pane 0..."
tmux -L "$SOCKET" send-keys -t "$SESSION".0 "$PLANNER_CMD" C-m

# Split window and start EXECUTER in pane 1
echo "Starting EXECUTER ($EXECUTER_CMD) in pane 1..."
tmux -L "$SOCKET" split-window -h -t "$SESSION" -c "$EXECUTER_CWD"
tmux -L "$SOCKET" send-keys -t "$SESSION".1 "$EXECUTER_CMD" C-m

# Wait for TUIs to initialize
echo "Waiting for TUIs to initialize..."
sleep 2

# Inject primer prompts if files exist
if [ -f "$PLANNER_PRIMER_FILE" ]; then
    echo "Injecting PLANNER primer..."
    # Read primer and send line by line
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            tmux -L "$SOCKET" send-keys -t "$SESSION".0 "$line" C-m
        else
            # Send just Enter for empty line
            tmux -L "$SOCKET" send-keys -t "$SESSION".0 C-m
        fi
    done < "$PLANNER_PRIMER_FILE"
else
    echo -e "${YELLOW}Warning: PLANNER primer file not found at $PLANNER_PRIMER_FILE${NC}"
    # Send a basic primer directly
    tmux -L "$SOCKET" send-keys -t "$SESSION".0 "You are PLANNER. When you finish thinking, emit a single tagged block:" C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".0 '[[POLI:MSG {"to":"EXECUTER","type":"plan","id":"$ID"}]]' C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".0 "<PLAN>" C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".0 "...natural language plan, step by step..." C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".0 "</PLAN>" C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".0 "[[/POLI:MSG]]" C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".0 "Do nothing else after emitting the block. Wait silently for the next user input." C-m
fi

if [ -f "$EXECUTER_PRIMER_FILE" ]; then
    echo "Injecting EXECUTER primer..."
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            tmux -L "$SOCKET" send-keys -t "$SESSION".1 "$line" C-m
        else
            # Send just Enter for empty line
            tmux -L "$SOCKET" send-keys -t "$SESSION".1 C-m
        fi
    done < "$EXECUTER_PRIMER_FILE"
else
    echo -e "${YELLOW}Warning: EXECUTER primer file not found at $EXECUTER_PRIMER_FILE${NC}"
    # Send a basic primer directly
    tmux -L "$SOCKET" send-keys -t "$SESSION".1 "You are EXECUTER. When you receive a plan, act on it. After you finish:" C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".1 "1) (Optional) Emit STATUS blocks for progress." C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".1 "2) Emit a final tagged block back to PLANNER:" C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".1 '[[POLI:MSG {"to":"PLANNER","type":"result","id":"$ID"}]]' C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".1 "<RESULT>" C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".1 "...concise result / notes / blockers..." C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".1 "</RESULT>" C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".1 "[[/POLI:MSG]]" C-m
    tmux -L "$SOCKET" send-keys -t "$SESSION".1 "After emitting the final block, wait silently for the next input." C-m
fi

echo -e "${GREEN}✓ tmux session ready!${NC}"
echo ""
echo "Session details:"
echo "  Socket: $SOCKET"
echo "  Session: $SESSION"
echo "  PLANNER: pane 0 (cwd: $PLANNER_CWD)"
echo "  EXECUTER: pane 1 (cwd: $EXECUTER_CWD)"
echo ""
echo "To attach and observe:"
echo "  tmux -L $SOCKET attach -t $SESSION"
echo ""
echo "To run orchestrator:"
echo "  python3 proto/poli_orchestrator.py"