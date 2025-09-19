#!/bin/bash
# Simple demo of PoliTerm Orchestrator

echo "🚀 PoliTerm Orchestrator Demo"
echo "=============================="
echo ""

# Setup mock environment
export PLANNER_CMD="python3 $(pwd)/tests/mock_planner.py"
export EXECUTER_CMD="python3 $(pwd)/tests/mock_executer.py"
export PLANNER_CWD="/tmp/poli_demo_planner"
export EXECUTER_CWD="/tmp/poli_demo_executer"

# Create working directories
mkdir -p "$PLANNER_CWD" "$EXECUTER_CWD"

echo "📋 Step 1: Starting tmux session with mock TUIs..."
bash scripts/bootstrap_tmux.sh

echo ""
echo "📋 Step 2: Session is ready!"
echo ""
echo "You can now:"
echo "  1. Watch the TUIs: tmux -L poli attach -t main"
echo "  2. Run a task: python3 proto/poli_orchestrator.py --task 'Your task here'"
echo "  3. Interactive mode: python3 proto/poli_orchestrator.py"
echo ""
echo "📋 Step 3: Running a demo task..."
echo ""

python3 proto/poli_orchestrator.py --task "Create a hello world file" --task-id "demo-$(date +%s)" &
ORCHESTRATOR_PID=$!

# Wait a bit for orchestrator to work
sleep 5

echo ""
echo "📋 Step 4: Checking results..."
echo ""
echo "PLANNER output (last 10 lines):"
tmux -L poli capture-pane -t main.0 -p | tail -10

echo ""
echo "EXECUTER output (last 10 lines):"
tmux -L poli capture-pane -t main.1 -p | tail -10

# Wait for orchestrator to finish
wait $ORCHESTRATOR_PID

echo ""
echo "✅ Demo complete!"
echo ""
echo "To clean up: bash scripts/kill_tmux.sh"
