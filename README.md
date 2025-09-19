# PoliTerm Orchestrator

A **working engine** that orchestrates two AI CLI TUIs (Planner and Executer) in a fully interactive TTY environment using tmux, without losing context.

## Overview

PoliTerm Orchestrator drives two Terminal User Interfaces (TUIs) in separate tmux panes, establishing an automated dialogue loop between a Planner AI and an Executer AI. The system maintains project-scoped sessions and preserves context across time.

## Architecture

```
+---------------------+       +---------------------+
|  tmux session 'main'|       |  Orchestrator (Py)  |
|  socket: -L poli    |       |---------------------|
|---------------------|       | - send_keys(pane..) |
| [pane 0] PLANNER    |<----->| - capture_tail(..)  |
|   cmd: claude       |  I/O  | - parse_blocks(..)  |
|   cwd: /ProjA       |       | - loop: Planner→Exec|
|---------------------|       |         →Planner... |
| [pane 1] EXECUTER   |       +---------------------+
|   cmd: codex        |
|   cwd: /ProjB       |
+---------------------+
```

## Prerequisites

- macOS or Linux
- `tmux` ≥ 3.x
- Python 3.10+ (stdlib only for MVP)
- Two AI CLI TUIs installed (e.g., `claude` for PLANNER, `codex` for EXECUTER)

## Quick Start

1. Configure environment (optional):
   ```bash
   source config/poli.env
   ```

2. Bootstrap tmux session with TUIs:
   ```bash
   bash scripts/bootstrap_tmux.sh
   ```

3. Run orchestrator:
   ```bash
   python3 proto/poli_orchestrator.py
   ```

4. Monitor panes (optional):
   ```bash
   tmux -L poli attach -t main
   ```

5. Cleanup when done:
   ```bash
   bash scripts/kill_tmux.sh
   ```

## Message Contract

The system uses tagged blocks for inter-TUI communication:

```text
[[POLI:MSG {"to":"EXECUTER","type":"plan","id":"<uuid>"}]]
<PLAN>
...natural language plan...
</PLAN>
[[/POLI:MSG]]
```

## Project Structure

```
politerm/
├─ README.md                # This file
├─ plan.md                  # Implementation plan
├─ scripts/
│  ├─ bootstrap_tmux.sh     # Creates tmux session/panes
│  └─ kill_tmux.sh          # Cleanup session
├─ proto/
│  └─ poli_orchestrator.py  # Orchestrator engine
├─ config/
│  ├─ poli.env              # Configuration
│  ├─ planner_primer.txt    # Planner initialization
│  └─ executer_primer.txt   # Executer initialization
└─ tests/
   ├─ smoke_loop.sh         # E2E smoke test
   ├─ mock_planner.py       # Planner simulator
   └─ mock_executer.py      # Executer simulator
```

## Configuration

Edit `config/poli.env` to customize:
- TUI commands (`PLANNER_CMD`, `EXECUTER_CMD`)
- Working directories (`PLANNER_CWD`, `EXECUTER_CWD`)
- Timeouts and other settings

## Testing

Run the smoke test:
```bash
bash tests/smoke_loop.sh
```

## Acceptance Criteria

- [x] Creates tmux session with two TUIs in correct working directories
- [x] Successfully injects primer prompts
- [x] Routes messages between Planner and Executer using tagged blocks
- [x] Preserves TUI context (attachable sessions)
- [x] Handles timeouts with clear messages

## Security Notes

- **Local only** for MVP - treats orchestrator as trusted local automation
- tmux socket should not be exposed externally
- For remote control in future: use mTLS/SSH tunnels

## Future Extensions (Phase 2+)

- Message bus (ZeroMQ IPC)
- Typed API (gRPC over UDS)
- UI/Monitor (xterm.js view)
- Multi-task queue
- Auto-resume on crash/restart

## License

MIT

## References

See `Politerm Architecture.md` for detailed design documentation.