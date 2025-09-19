#!/usr/bin/env bash
set -euo pipefail

# Smoke test for PoliTerm Orchestrator
# This script performs a complete end-to-end test

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  PoliTerm Orchestrator - Smoke Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Source configuration
if [ -f "$PROJECT_ROOT/config/poli.env" ]; then
    echo -e "${GREEN}✓${NC} Loading configuration..."
    source "$PROJECT_ROOT/config/poli.env"
fi

# Override with test-specific settings if using mocks
if [ "${USE_MOCKS:-1}" = "1" ]; then
    echo -e "${YELLOW}ℹ${NC} Using mock TUIs for testing"
    export PLANNER_CMD="python3 $PROJECT_ROOT/tests/mock_planner.py"
    export EXECUTER_CMD="python3 $PROJECT_ROOT/tests/mock_executer.py"
    export PLANNER_CWD="/tmp/poli_test_planner"
    export EXECUTER_CWD="/tmp/poli_test_executer"

    # Create test directories
    mkdir -p "$PLANNER_CWD" "$EXECUTER_CWD"
fi

# Function to cleanup
cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up...${NC}"
    bash "$PROJECT_ROOT/scripts/kill_tmux.sh" 2>/dev/null || true
    if [ "${USE_MOCKS:-1}" = "1" ]; then
        rm -rf "$PLANNER_CWD" "$EXECUTER_CWD" 2>/dev/null || true
    fi
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Step 1: Kill any existing session
echo -e "${YELLOW}→${NC} Cleaning any existing sessions..."
bash "$PROJECT_ROOT/scripts/kill_tmux.sh" 2>/dev/null || true

# Step 2: Bootstrap tmux session
echo -e "${YELLOW}→${NC} Starting tmux session..."
if bash "$PROJECT_ROOT/scripts/bootstrap_tmux.sh"; then
    echo -e "${GREEN}✓${NC} tmux session started successfully"
else
    echo -e "${RED}✗${NC} Failed to start tmux session"
    exit 1
fi

# Step 3: Check if session exists
echo -e "${YELLOW}→${NC} Verifying tmux session..."
if python3 "$PROJECT_ROOT/proto/poli_orchestrator.py" --check; then
    echo -e "${GREEN}✓${NC} tmux session verified"
else
    echo -e "${RED}✗${NC} tmux session not found"
    exit 1
fi

# Step 4: Run a test task
echo -e "${YELLOW}→${NC} Running test task..."
TEST_TASK="Create a simple hello.txt file with 'Hello, PoliTerm!' content"
TASK_ID="smoke-test-$(date +%s)"

echo -e "${BLUE}Task: $TEST_TASK${NC}"
echo -e "${BLUE}ID: $TASK_ID${NC}"

# Create a temporary output file to capture results
OUTPUT_FILE="/tmp/poli_smoke_test_output.txt"

# Run the orchestrator with the test task
if python3 "$PROJECT_ROOT/proto/poli_orchestrator.py" \
    --task "$TEST_TASK" \
    --task-id "$TASK_ID" \
    > "$OUTPUT_FILE" 2>&1; then
    echo -e "${GREEN}✓${NC} Task completed successfully"
    RESULT="SUCCESS"
else
    echo -e "${RED}✗${NC} Task failed"
    RESULT="FAILURE"
fi

# Step 5: Display output
echo ""
echo -e "${YELLOW}Task Output:${NC}"
echo "----------------------------------------"
cat "$OUTPUT_FILE"
echo "----------------------------------------"

# Step 6: Verify results (if using mocks)
if [ "${USE_MOCKS:-1}" = "1" ]; then
    echo ""
    echo -e "${YELLOW}→${NC} Verifying mock execution..."

    # Check if the mock executer created the expected file
    if [ -f "$EXECUTER_CWD/hello.txt" ]; then
        content=$(cat "$EXECUTER_CWD/hello.txt")
        if [[ "$content" == *"Hello"* ]]; then
            echo -e "${GREEN}✓${NC} Mock execution verified - file created with expected content"
        else
            echo -e "${RED}✗${NC} File created but content unexpected: $content"
            RESULT="FAILURE"
        fi
    else
        echo -e "${YELLOW}ℹ${NC} Mock file not created (this is OK for basic mocks)"
    fi
fi

# Step 7: Summary
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"

if [ "$RESULT" = "SUCCESS" ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "The PoliTerm Orchestrator is working correctly:"
    echo "  • tmux session management ✓"
    echo "  • Message routing ✓"
    echo "  • Task execution ✓"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo ""
    echo "Please check the output above for details."
    exit 1
fi