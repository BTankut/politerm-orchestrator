#!/usr/bin/env bash
set -euo pipefail

# Bootstrap script V2 - Uses SHARED workspace for both TUIs

# Configuration from environment or defaults
SOCKET="${POLI_TMUX_SOCKET:-poli}"
SESSION="${POLI_TMUX_SESSION:-main}"

# CRITICAL: Both TUIs use the SAME directory
PROJECT_DIR="${PROJECT_DIR:-$(pwd)}"
PLANNER_CWD="${PLANNER_CWD:-$PROJECT_DIR}"
EXECUTER_CWD="${EXECUTER_CWD:-$PROJECT_DIR}"

# Ensure they're the same (safety check)
if [ "$PLANNER_CWD" != "$EXECUTER_CWD" ]; then
    echo "⚠️  WARNING: PLANNER and EXECUTER have different working directories!"
    echo "   PLANNER_CWD:  $PLANNER_CWD"
    echo "   EXECUTER_CWD: $EXECUTER_CWD"
    echo ""
    echo "For proper context sharing, they MUST use the same directory."
    echo "Setting both to: $PROJECT_DIR"
    PLANNER_CWD="$PROJECT_DIR"
    EXECUTER_CWD="$PROJECT_DIR"
fi

PLANNER_CMD="${PLANNER_CMD:-claude}"
EXECUTER_CMD="${EXECUTER_CMD:-codex}"

# Paths to primer files
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_DIR="$SCRIPT_DIR/../config"

# Use newest primers if they exist (v3 > v2 > legacy)
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
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting PoliTerm Orchestrator tmux session V2...${NC}"
echo -e "${BLUE}SHARED WORKSPACE: $PROJECT_DIR${NC}"

# Check if session already exists
if tmux -L "$SOCKET" has-session -t "$SESSION" 2>/dev/null; then
    echo -e "${YELLOW}Warning: Session '$SESSION' already exists on socket '$SOCKET'${NC}"
    echo "Kill it first with: bash scripts/kill_tmux.sh"
    exit 1
fi

# Create/verify working directory
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}Creating project directory: $PROJECT_DIR${NC}"
    mkdir -p "$PROJECT_DIR"
fi

# Show what's in the directory
echo -e "${BLUE}Project directory contents:${NC}"
ls -la "$PROJECT_DIR" 2>/dev/null | head -10 || echo "  (empty or new directory)"

# Create new tmux session in the PROJECT directory
echo "Creating tmux session '$SESSION' on socket '$SOCKET'..."
echo "  Both panes will start in: $PROJECT_DIR"
tmux -L "$SOCKET" -f /dev/null new-session -d -s "$SESSION" -c "$PROJECT_DIR"

# Start PLANNER in pane 0 (already in PROJECT_DIR)
echo "Starting PLANNER ($PLANNER_CMD) in pane 0..."
tmux -L "$SOCKET" send-keys -t "$SESSION".0 "$PLANNER_CMD" C-m

# Split window and start EXECUTER in pane 1 (also in PROJECT_DIR)
echo "Starting EXECUTER ($EXECUTER_CMD) in pane 1..."
tmux -L "$SOCKET" split-window -h -t "$SESSION" -c "$PROJECT_DIR"
tmux -L "$SOCKET" send-keys -t "$SESSION".1 "$EXECUTER_CMD" C-m

# Wait for TUIs to initialize
echo "Waiting for TUIs to initialize..."
sleep 2

# Inject primer prompts if files exist
if [ -f "$PLANNER_PRIMER_FILE" ]; then
    echo "Injecting PLANNER primer (continuous dialogue mode)..."
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            tmux -L "$SOCKET" send-keys -t "$SESSION".0 "$line" C-m
        else
            tmux -L "$SOCKET" send-keys -t "$SESSION".0 C-m
        fi
    done < "$PLANNER_PRIMER_FILE"
else
    echo -e "${YELLOW}Warning: PLANNER primer file not found${NC}"
fi

if [ -f "$EXECUTER_PRIMER_FILE" ]; then
    echo "Injecting EXECUTER primer (continuous dialogue mode)..."
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            tmux -L "$SOCKET" send-keys -t "$SESSION".1 "$line" C-m
        else
            tmux -L "$SOCKET" send-keys -t "$SESSION".1 C-m
        fi
    done < "$EXECUTER_PRIMER_FILE"
else
    echo -e "${YELLOW}Warning: EXECUTER primer file not found${NC}"
fi

echo -e "${GREEN}✓ tmux session ready!${NC}"
echo ""
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo "Session Configuration:"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo "  Socket:      $SOCKET"
echo "  Session:     $SESSION"
echo "  Project Dir: $PROJECT_DIR"
echo ""
echo "  PLANNER:"
echo "    Pane:      0"
echo "    Command:   $PLANNER_CMD"
echo "    CWD:       $PLANNER_CWD"
echo ""
echo "  EXECUTER:"
echo "    Pane:      1"
echo "    Command:   $EXECUTER_CMD"
echo "    CWD:       $EXECUTER_CWD"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""
echo "Commands:"
echo "  Watch TUIs:   tmux -L $SOCKET attach -t $SESSION"
echo "  Orchestrator: python3 proto/poli_orchestrator_v2.py"
echo "  Clean up:     bash scripts/kill_tmux.sh"