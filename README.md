# PoliTerm Orchestrator 🤖

An intelligent orchestration system that keeps AI CLI tools (Planner and Executer) in continuous dialogue inside tmux-managed terminals, creating a powerful autonomous task execution environment.

## 🌟 Features

- **Dual AI System**: Coordinates two AI CLI tools - a Planner that creates strategies and an Executer that implements them
- **Continuous Dialogue**: Maintains ongoing conversation between AIs until task completion
- **Context Preservation**: Both AIs work in the same directory, sharing full project context
- **State Tracking**: Monitors task progress with comprehensive state management
- **Interrupt Handling**: Graceful shutdown with Ctrl+C
- **Real CLI Support**: Works with claude, codex, aider, and other AI CLI tools
- **Flexible tmux Layouts**: Choose between a single tmux window with split panes or dedicated planner/executer tmux sessions (each in its own OS terminal window)
- **Mock Testing**: Includes mock TUIs for testing without API costs

## 🏗️ Architecture

```
tmux socket: poli

┌───────────────┐       ┌──────────────────────┐
│ session:planner│       │  Orchestrator (Py)   │
│ window: tui    │<----->│ - send_keys()         │
│ pane 0: PLANNER│  I/O  │ - capture_tail()      │
│ cwd: /project  │       │ - parse POLI blocks   │
└───────────────┘       │ - continuous routing  │
                        └──────────────────────┘
┌────────────────┐
│session:executer │
│window: tui      │
│pane 0: EXECUTER │
│cwd: /project    │
└────────────────┘

(GUI wizard can alternatively launch a single `main` session with split panes.)
```

## 📋 Prerequisites

- macOS or Linux
- `tmux` ≥ 3.x
- Python 3.10+
- AI CLI tools (at least one):
  - `claude` (Claude Code)
  - `codex` (Codex CLI)
  - `aider` (Git-aware AI)
  - Or any compatible AI CLI

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/BTankut/politerm-orchestrator.git
cd politerm-orchestrator
```

### 2. Install tmux (if not installed)
```bash
# macOS
brew install tmux

# Ubuntu/Debian
sudo apt-get install tmux
```

### 3. Start PoliTerm in your project
```bash
# Navigate to your project directory
cd /path/to/your/project

# Single-command launch (wizard + orchestrator)
./scripts/poli_start.sh

# Alternatively, run the components manually
/opt/homebrew/bin/python3.9 proto/poli_session_wizard.py
python3 proto/poli_orchestrator_v3.py --monitor

# Legacy shell helper if you prefer bash
./start_project.sh
```

- GUI wizard lets you pick planner/executer modes with one click:
  - Planner: `claude`, `claude --continue`, `claude --dangerously-skip-permissions`, `claude --continue --dangerously-skip-permissions`
  - Executer: `codex`, `codex resume --last`, `codex resume --yolo`, `codex resume --last --yolo`
- You can enter custom commands and toggle tmux logging/auto-attach and choose pane layout (split panes vs separate windows).
- Without a display you can fall back to the text wizard via `python3 proto/poli_session_wizard.py --cli`.
  - Primer injection waits a configurable delay and checks CLI readiness to avoid racing with startup banners. Tune with `POLI_PRIMER_DELAY` (default 3s) and `POLI_READY_TIMEOUT` (default 8s).

### 4. Run a task
```bash
# Using the orchestrator
python3 proto/poli_orchestrator_v3.py --task "Create a REST API with user authentication"

# Or interactive mode
python3 proto/poli_orchestrator_v3.py
```

### 5. Watch the AIs work
When you choose **separate windows**, the wizard opens two Terminal.app windows automatically. Attach manually if needed:

```bash
# Planner window
tmux -L poli attach -t planner

# Executer window
tmux -L poli attach -t executer
```

For the classic split-pane layout:

```bash
tmux -L poli attach -t main
```

## 🎯 Usage Examples

### Basic Task Execution
```bash
python3 proto/poli_orchestrator_v3.py --task "Analyze this codebase and create documentation"
```

### With Custom Rounds
```bash
python3 proto/poli_orchestrator_v3.py --task "Refactor the database module" --max-rounds 15
```

### Interactive Mode
```bash
python3 proto/poli_orchestrator_v3.py
# Then type your tasks interactively
```

## 🔧 Configuration

### Environment Variables
Create or edit `config/shared_workspace.env`:

```bash
# Project directory (both AIs will work here)
export PROJECT_DIR="/path/to/your/project"

# AI CLI commands
export PLANNER_CMD="claude"    # or any AI CLI
export EXECUTER_CMD="codex"    # or any AI CLI

# Timeouts
export POLI_PLAN_TIMEOUT=300   # 5 minutes
export POLI_EXEC_TIMEOUT=900   # 15 minutes

# Max dialogue rounds
export POLI_MAX_ROUNDS=20
```

### Using Different AI Combinations

```bash
# Claude + Claude
export PLANNER_CMD="claude"
export EXECUTER_CMD="claude"

# Claude + Aider (great for git projects)
export PLANNER_CMD="claude"
export EXECUTER_CMD="aider"

# Any combination works!
```

## 📁 Project Structure

```
politerm-orchestrator/
├── proto/                      # Orchestrator implementations
│   ├── poli_orchestrator.py    # v1: Single round
│   ├── poli_orchestrator_v2.py # v2: Continuous dialogue
│   ├── poli_orchestrator_v3.py # v3: Full features (recommended)
│   └── poli_session_wizard.py  # Interactive startup wizard
├── scripts/                     # tmux management
│   ├── bootstrap_tmux_v2.sh    # Start tmux session
│   └── kill_tmux.sh            # Clean up
├── config/                      # Configuration files
│   ├── shared_workspace.env    # Environment settings
│   ├── planner_primer_v3.txt   # Planner interactive primer
│   ├── executer_primer_v3.txt  # Executer interactive primer
│   ├── planner_primer_v2.txt   # Legacy primer
│   └── executer_primer_v2.txt  # Legacy primer
├── tests/                       # Testing utilities
│   ├── mock_planner.py         # Mock planner for testing
│   └── mock_executer.py        # Mock executer for testing
└── start_project.sh            # Legacy startup helper
```

## 🔄 How It Works

1. **Initialization**: Two AI CLI tools are started as either split panes in one tmux window or as dedicated tmux sessions (default)
2. **Role Assignment**: Each AI receives a "primer" explaining its role
3. **Task Submission**: User provides a task through the orchestrator
4. **Planning Phase**: PLANNER creates a detailed strategy
5. **Execution Phase**: EXECUTER implements the plan
6. **Review Loop**: PLANNER reviews results and provides next steps
7. **Completion**: Loop continues until PLANNER signals task completion

## 🧪 Testing with Mocks

Test without using API credits:

```bash
# Set up mock environment
export PLANNER_CMD="python3 $(pwd)/tests/mock_planner.py"
export EXECUTER_CMD="python3 $(pwd)/tests/mock_executer.py"

# Run test (pane layout for quick smoke)
bash scripts/bootstrap_tmux_v2.sh
python3 proto/poli_orchestrator_v3.py --task "Test task"
```

## 📝 Message Protocol

The system uses tagged blocks for inter-AI communication:

```
[[POLI:MSG {"to":"EXECUTER","type":"plan","id":"task-123"}]]
<PLAN>
Step 1: Analyze requirements
Step 2: Create implementation
Step 3: Test and verify
</PLAN>
[[/POLI:MSG]]
```

## 🛠️ Advanced Features

### State Tracking
```bash
# Check task states
python3 proto/poli_orchestrator_v3.py --state
```

### Interrupt Handling
- Press `Ctrl+C` to gracefully stop both AIs
- State is logged for debugging

### Custom Primers
Edit primer files in `config/` to customize AI behavior for your specific needs.

## 🐛 Troubleshooting

### tmux session issues
```bash
# Kill existing session
bash scripts/kill_tmux.sh

# Verify no session exists
tmux -L poli list-sessions
```

If the wizard launched separate sessions and you want to inspect them:

```bash
tmux -L poli attach -t planner
tmux -L poli attach -t executer
```

### API Key Setup
```bash
# For Claude
export ANTHROPIC_API_KEY="your-key"

# For OpenAI-based tools
export OPENAI_API_KEY="your-key"
```

### View Logs
```bash
# Check orchestrator logs
tail -f logs/poli_orchestrator.log

# View tmux sessions directly
tmux -L poli attach -t planner
tmux -L poli attach -t executer

# Or, for the split layout
tmux -L poli attach -t main
```

## 📚 Documentation

- [Architecture Document](Politerm%20Architecture.md) - Detailed system design
- [Implementation Plan](plan.md) - Development roadmap
- [AI CLI Guide](AI_CLI_GUIDE.md) - Supported AI tools

## 🚦 Version History

- **v3.0** - Full architecture compliance, state tracking, interrupt handling
- **v2.0** - Continuous dialogue implementation
- **v1.0** - Basic single-round orchestration

## 📄 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 🙏 Acknowledgments

- Built for orchestrating AI CLI tools like Claude, Codex, and Aider
- Uses tmux for robust terminal multiplexing
- Inspired by the need for autonomous AI collaboration

## 📮 Contact

- GitHub: [@BTankut](https://github.com/BTankut)
- Issues: [GitHub Issues](https://github.com/BTankut/politerm-orchestrator/issues)

---

**Note**: This is a stable v1.0 release. Phase-2 features (ZeroMQ, gRPC, Web UI) are planned for future releases.
