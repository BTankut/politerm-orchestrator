#!/bin/bash
# Start PoliTerm in a specific project directory

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo -e "${BLUE}  PoliTerm Project Orchestrator${NC}"
echo -e "${BLUE}═══════════════════════════════════════${NC}"
echo ""

# Get project directory from argument, environment, or use current directory
if [ $# -eq 1 ]; then
    PROJECT_DIR="$1"
    # Convert to absolute path
    PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
elif [ -n "${PROJECT_DIR:-}" ]; then
    # Use environment variable if set
    PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
else
    PROJECT_DIR="$(pwd)"
fi

# Check if directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}Error: Directory does not exist: $PROJECT_DIR${NC}"
    echo "Please provide a valid project directory."
    exit 1
fi

echo -e "${GREEN}Project Directory: $PROJECT_DIR${NC}"

# Check for important project files
echo ""
echo "Project Analysis:"
if [ -f "$PROJECT_DIR/package.json" ]; then
    echo "  ✓ Node.js project detected (package.json)"
fi
if [ -f "$PROJECT_DIR/requirements.txt" ] || [ -f "$PROJECT_DIR/pyproject.toml" ]; then
    echo "  ✓ Python project detected"
fi
if [ -f "$PROJECT_DIR/Cargo.toml" ]; then
    echo "  ✓ Rust project detected (Cargo.toml)"
fi
if [ -f "$PROJECT_DIR/go.mod" ]; then
    echo "  ✓ Go project detected (go.mod)"
fi
if [ -d "$PROJECT_DIR/.git" ]; then
    echo "  ✓ Git repository"
    # Show current branch
    cd "$PROJECT_DIR" && echo "  → Branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
fi

echo ""

# Export the project directory
export PROJECT_DIR="$PROJECT_DIR"
export PLANNER_CWD="$PROJECT_DIR"
export EXECUTER_CWD="$PROJECT_DIR"

# Load shared workspace config
source config/shared_workspace.env

# Choose TUI commands
echo "Select AI CLI configuration:"
echo "  1. Mock TUIs (for testing)"
echo "  2. Real Claude + Codex"
echo "  3. Double Claude (two instances)"
echo "  4. Custom"
read -p "Choice (1-4): " choice

case $choice in
    1)
        export PLANNER_CMD="python3 $(pwd)/tests/mock_planner.py"
        export EXECUTER_CMD="python3 $(pwd)/tests/mock_executer.py"
        echo -e "${YELLOW}Using Mock TUIs${NC}"
        ;;
    2)
        export PLANNER_CMD="claude"
        export EXECUTER_CMD="codex"
        echo -e "${GREEN}Using Claude (Planner) + Codex (Executer)${NC}"
        ;;
    3)
        export PLANNER_CMD="claude"
        export EXECUTER_CMD="claude"
        echo -e "${GREEN}Using Double Claude${NC}"
        ;;
    4)
        read -p "Enter PLANNER command: " PLANNER_CMD
        read -p "Enter EXECUTER command: " EXECUTER_CMD
        export PLANNER_CMD
        export EXECUTER_CMD
        echo -e "${GREEN}Using custom: $PLANNER_CMD + $EXECUTER_CMD${NC}"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

# Kill any existing session
echo ""
echo "Cleaning up old sessions..."
bash scripts/kill_tmux.sh 2>/dev/null || true

# Start new session
echo "Starting tmux session..."
bash scripts/bootstrap_tmux_v2.sh

echo ""
echo -e "${GREEN}✨ Ready to orchestrate in: $PROJECT_DIR${NC}"
echo ""
echo "Next steps:"
echo "  1. Run orchestrator:"
echo "     python3 proto/poli_orchestrator_v2.py"
echo ""
echo "  2. Watch TUIs (in another terminal):"
echo "     tmux -L poli attach -t main"
echo ""

# Ask if user wants to start orchestrator
read -p "Start orchestrator now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 proto/poli_orchestrator_v2.py
fi