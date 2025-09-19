#!/bin/bash
# PoliTerm Orchestrator - Real CLI Runner
# Bu script gerçek AI CLI'larla (claude, codex) sistemi çalıştırır

set -euo pipefail

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  PoliTerm - Real AI CLI Orchestrator${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Load real CLI configuration
source config/real_cli.env

# Create working directories
echo -e "${YELLOW}→${NC} Creating working directories..."
mkdir -p "$PLANNER_CWD" "$EXECUTER_CWD"
mkdir -p logs

# Check if CLIs are available
echo -e "${YELLOW}→${NC} Checking AI CLIs..."
if command -v "$PLANNER_CMD" &> /dev/null; then
    echo -e "${GREEN}✓${NC} PLANNER: $PLANNER_CMD found"
else
    echo -e "${YELLOW}⚠${NC} PLANNER: $PLANNER_CMD not found"
    echo "Install with: brew install claude-cmd"
fi

if command -v "$EXECUTER_CMD" &> /dev/null; then
    echo -e "${GREEN}✓${NC} EXECUTER: $EXECUTER_CMD found"
else
    echo -e "${YELLOW}⚠${NC} EXECUTER: $EXECUTER_CMD not found"
    echo "Install with: brew install codex-cli"
fi

echo ""

# Kill any existing session
echo -e "${YELLOW}→${NC} Cleaning up old sessions..."
bash scripts/kill_tmux.sh 2>/dev/null || true

# Start new session
echo -e "${YELLOW}→${NC} Starting tmux session with real AI CLIs..."
bash scripts/bootstrap_tmux.sh

echo ""
echo -e "${GREEN}✅ Real AI CLI session ready!${NC}"
echo ""
echo "Available commands:"
echo "  ${BLUE}1.${NC} Watch TUIs:     tmux -L poli attach -t main"
echo "  ${BLUE}2.${NC} Run a task:     python3 proto/poli_orchestrator.py --task 'Your task'"
echo "  ${BLUE}3.${NC} Interactive:    python3 proto/poli_orchestrator.py"
echo "  ${BLUE}4.${NC} Clean up:       bash scripts/kill_tmux.sh"
echo ""
echo -e "${YELLOW}Note:${NC} Real CLIs may need API keys configured"
echo ""

# Optional: Start interactive orchestrator
read -p "Start interactive orchestrator? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 proto/poli_orchestrator.py
fi