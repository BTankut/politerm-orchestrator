#!/usr/bin/env python3
"""PoliTerm session wizard with Tkinter GUI and CLI fallback."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except Exception:  # pragma: no cover
    tk = None
    filedialog = None
    messagebox = None
    ttk = None

if tk is None and os.environ.get("POLI_WIZARD_ALT_EXEC") != "1":
    for candidate in ("python3.11", "python3.10", "python3.9", "python3.12", "python3.13"):
        alt = shutil.which(candidate)
        if not alt:
            continue
        try:
            subprocess.run([alt, "-c", "import tkinter"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            continue
        os.environ["POLI_WIZARD_ALT_EXEC"] = "1"
        os.execv(alt, [alt, str(Path(__file__).resolve())] + sys.argv[1:])
    print(
        "tkinter not available; falling back to CLI. Install via `python3 -m pip install tk` "
        "or Homebrew `brew install python-tk@3.9`."
    )

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CONFIG_DIR = REPO_ROOT / "config"
LOG_DIR = REPO_ROOT / "logs"

DEFAULT_SOCKET = os.environ.get("POLI_TMUX_SOCKET", "poli")
DEFAULT_SESSION = os.environ.get("POLI_TMUX_SESSION", "main")
DEFAULT_PLANNER_SESSION = os.environ.get("POLI_TMUX_PLANNER_SESSION", "planner")
DEFAULT_EXECUTER_SESSION = os.environ.get("POLI_TMUX_EXECUTER_SESSION", "executer")
DEFAULT_ROLE_WINDOW = os.environ.get("POLI_TMUX_ROLE_WINDOW", "tui")
SESSION_STATE_FILE = CONFIG_DIR / "last_session.json"
DEBUG_TMUX = os.environ.get("POLI_WIZARD_DEBUG", "1").lower() not in ("0", "false", "no")
AUTO_ATTACH = os.environ.get("POLI_WIZARD_ATTACH", "1").lower() not in ("0", "false", "no")
INSIDE_TMUX = bool(os.environ.get("TMUX"))
PRIMER_DELAY = float(os.environ.get("POLI_PRIMER_DELAY", "3.0"))
READY_TIMEOUT = float(os.environ.get("POLI_READY_TIMEOUT", "10.0"))
READY_IDLE = float(os.environ.get("POLI_READY_IDLE", "1.0"))
PANE_LOG = os.environ.get("POLI_PANE_LOG", "").lower() in ("1", "true", "on")

CUSTOM_LABEL = "Custom command"

PLANNER_MODES: List[Tuple[str, str]] = [
    ("Standard (claude)", "claude"),
    ("Continue (claude --continue)", "claude --continue"),
    ("Dangerous skip (claude --dangerously-skip-permissions)", "claude --dangerously-skip-permissions"),
    (
        "Continue + dangerous skip (claude --continue --dangerously-skip-permissions)",
        "claude --continue --dangerously-skip-permissions",
    ),
]
EXECUTER_MODES: List[Tuple[str, str]] = [
    ("Standard (codex)", "codex"),
    ("Resume (codex resume --last)", "codex resume --last"),
    ("YOLO (codex resume --yolo)", "codex resume --yolo"),
    ("Resume + YOLO (codex resume --last --yolo)", "codex resume --last --yolo"),
]


@dataclass
class SessionConfig:
    project_dir: Path
    planner_cmd: str
    executer_cmd: str
    socket: str = DEFAULT_SOCKET
    session: str = DEFAULT_SESSION
    planner_session: str = DEFAULT_PLANNER_SESSION
    executer_session: str = DEFAULT_EXECUTER_SESSION
    window_name: str = DEFAULT_ROLE_WINDOW

    @property
    def planner_cwd(self) -> Path:
        return self.project_dir

    @property
    def executer_cwd(self) -> Path:
        return self.project_dir


def run_tmux_command(
    args: List[str],
    *,
    check: bool = True,
    capture: bool = True,
    desc: Optional[str] = None,
    stdin: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess:
    cmd_display = " ".join(args)
    prefix = f"[tmux:{desc}] " if desc else "[tmux] "
    if DEBUG_TMUX:
        print(prefix + cmd_display)
    try:
        result = subprocess.run(
            args,
            text=True,
            capture_output=capture,
            check=check,
            input=stdin,
            env=env,
        )
        if DEBUG_TMUX and capture:
            if result.stdout:
                print(prefix + "stdout: " + result.stdout.strip())
            if result.stderr:
                print(prefix + "stderr: " + result.stderr.strip())
        return result
    except subprocess.CalledProcessError as exc:
        if capture:
            if exc.stdout:
                print(prefix + "stdout: " + exc.stdout.strip())
            if exc.stderr:
                print(prefix + "stderr: " + exc.stderr.strip())
        elif DEBUG_TMUX:
            print(prefix + f"command failed with return code {exc.returncode}")
        if DEBUG_TMUX:
            print(prefix + f"ERROR running command: {cmd_display}")
        if check:
            raise
        return exc


def tmux_socket_args(socket: str) -> List[str]:
    return ["tmux", "-L", socket]


def kill_existing_sessions(config: SessionConfig) -> None:
    args = tmux_socket_args(config.socket)
    targets = [config.session, config.planner_session, config.executer_session]
    killed_any = False

    for session_name in dict.fromkeys(filter(None, targets)):
        result = run_tmux_command(
            args + ["has-session", "-t", session_name],
            check=False,
            capture=False,
            desc=f"has-session:{session_name}",
        )
        if isinstance(result, subprocess.CompletedProcess) and result.returncode == 0:
            if not killed_any:
                print("\n⚠️  Existing PoliTerm sessions detected. Cleaning up...")
                killed_any = True
            run_tmux_command(
                args + ["kill-session", "-t", session_name],
                check=False,
                capture=False,
                desc=f"kill-session:{session_name}",
            )

    server_check = run_tmux_command(
        args + ["list-sessions"],
        check=False,
        desc="list-sessions",
    )
    if isinstance(server_check, subprocess.CompletedProcess):
        still_running = server_check.returncode == 0 and bool(server_check.stdout.strip())
        if not still_running:
            run_tmux_command(
                args + ["kill-server"],
                check=False,
                capture=False,
                desc="kill-server",
            )
    if killed_any:
        time.sleep(0.5)


def apply_minimal_tmux_ui(args: List[str]) -> None:
    # Apply minimal UI settings regardless of server startup config
    run_tmux_command(args + ["set", "-g", "status", "off"], desc="ui:status-off", check=False, capture=False)
    run_tmux_command(args + ["set", "-g", "mouse", "off"], desc="ui:mouse-off", check=False, capture=False)
    run_tmux_command(args + ["set", "-g", "prefix", "None"], desc="ui:prefix-none", check=False, capture=False)
    run_tmux_command(args + ["unbind", "C-b"], desc="ui:unbind-C-b", check=False, capture=False)


def start_tmux_topology(config: SessionConfig, layout: str) -> None:
    args = tmux_socket_args(config.socket)
    tmux_conf = REPO_ROOT / "config" / "tmux_min.conf"
    conf_args = ["-f", str(tmux_conf)] if tmux_conf.exists() else ["-f", "/dev/null"]
    shell = os.environ.get("SHELL", "/bin/bash")

    if layout == "split":
        # Start planner with command at session creation
        run_tmux_command(
            args
            + conf_args
            + [
                "new-session",
                "-d",
                "-s",
                config.session,
                "-c",
                str(config.planner_cwd),
                shell,
                "-lc",
                config.planner_cmd,
            ],
            desc="new-session:main+planner",
        )

        # Split and start executer with its command directly
        run_tmux_command(
            args
            + [
                "split-window",
                "-h",
                "-t",
                config.session,
                "-c",
                str(config.executer_cwd),
                shell,
                "-lc",
                config.executer_cmd,
            ],
            desc="split-window+executer",
        )
    else:
        for role, session_name, cwd, cmd in (
            ("planner", config.planner_session, config.planner_cwd, config.planner_cmd),
            ("executer", config.executer_session, config.executer_cwd, config.executer_cmd),
        ):
            run_tmux_command(
                args
                + conf_args
                + [
                    "new-session",
                    "-d",
                    "-s",
                    session_name,
                    "-n",
                    config.window_name,
                    "-c",
                    str(cwd),
                    shell,
                    "-lc",
                    cmd,
                ],
                desc=f"new-session:{role}",
            )

    # Apply minimal UI settings at server level too (in case server already existed)
    apply_minimal_tmux_ui(args)
    # Minimal settle for tmux server; full primer delay is applied in orchestrate()
    time.sleep(0.5)


def _sanitize_cli_line(line: str) -> str:
    s = line
    stripped = s.lstrip()
    if stripped.startswith('/'):
        prefix_len = len(s) - len(stripped)
        s = s[:prefix_len] + "\u200B/" + stripped[1:]
    return s


def send_lines_to_target(config: SessionConfig, target: str, lines: List[str]) -> None:
    args = tmux_socket_args(config.socket)
    sanitized_lines = [_sanitize_cli_line(l) for l in lines]
    block = "\n".join(sanitized_lines).rstrip("\n")

    # For codex-like TUIs, prefer typing with Ctrl-J newlines (avoid -l to allow leading '-')
    prefer_literal = ":executer." in target or target.startswith("executer:")

    if prefer_literal:
        for i, line in enumerate(block.split("\n")):
            if line:
                run_tmux_command(
                    args + ["send-keys", "-t", target, "--", line],
                    desc=f"{target}:type",
                    capture=False,
                )
            if i < len(block.split("\n")) - 1:
                run_tmux_command(
                    args + ["send-keys", "-t", target, "C-j"],
                    desc=f"{target}:newline",
                    capture=False,
                )
                time.sleep(0.02)
        run_tmux_command(
            args + ["send-keys", "-t", target, "C-m"],
            desc=f"{target}:send",
            capture=False,
        )
        time.sleep(0.05)
        return

    if block:
        preview = block.replace("\n", " ⏎ ")
        if len(preview) > 60:
            preview = preview[:57] + "..."
        run_tmux_command(
            args + ["load-buffer", "-"],
            desc=f"{target}:load-buffer '{preview}'",
            capture=False,
            stdin=block + "\n",
        )
        time.sleep(0.1)
        run_tmux_command(
            args + ["paste-buffer", "-d", "-t", target],
            desc=f"{target}:paste",
            capture=False,
        )
        time.sleep(0.1)
    run_tmux_command(
        args + ["send-keys", "-t", target, "C-m"],
        desc=f"{target}:enter",
        capture=False,
    )
    time.sleep(0.05)


def persist_session(config: SessionConfig, debug_tmux: bool, auto_attach: bool, layout: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    CONFIG_DIR.mkdir(exist_ok=True)
    data = {
        "project_dir": str(config.project_dir),
        "planner_cmd": config.planner_cmd,
        "executer_cmd": config.executer_cmd,
        "socket": config.socket,
        "session": config.session,
        "planner_session": config.planner_session,
        "executer_session": config.executer_session,
        "window_name": config.window_name,
        "debug_tmux": bool(debug_tmux),
        "auto_attach": bool(auto_attach),
        "layout": layout,
        "saved_at": time.time(),
    }
    SESSION_STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_previous_session() -> Tuple[Optional[SessionConfig], Dict[str, object]]:
    prefs: Dict[str, object] = {
        "debug_tmux": DEBUG_TMUX,
        "auto_attach": AUTO_ATTACH,
        "layout": "split",
    }
    if not SESSION_STATE_FILE.exists():
        return None, prefs
    try:
        data = json.loads(SESSION_STATE_FILE.read_text(encoding="utf-8"))
        config = SessionConfig(
            project_dir=Path(data["project_dir"]).expanduser(),
            planner_cmd=data["planner_cmd"],
            executer_cmd=data["executer_cmd"],
            socket=data.get("socket", DEFAULT_SOCKET),
            session=data.get("session", DEFAULT_SESSION),
            planner_session=data.get("planner_session", DEFAULT_PLANNER_SESSION),
            executer_session=data.get("executer_session", DEFAULT_EXECUTER_SESSION),
            window_name=data.get("window_name", DEFAULT_ROLE_WINDOW),
        )
        prefs["debug_tmux"] = bool(data.get("debug_tmux", prefs["debug_tmux"]))
        prefs["auto_attach"] = bool(data.get("auto_attach", prefs["auto_attach"]))
        prefs["layout"] = data.get("layout", prefs["layout"])
        return config, prefs
    except Exception:
        return None, prefs


def attach_tmux_sessions(config: SessionConfig, auto_attach: bool, layout: str) -> None:
    has_tty = sys.stdin.isatty() and sys.stdout.isatty()
    if INSIDE_TMUX or not has_tty or not auto_attach:
        if layout == "split":
            print(
                f"\nTmux ready. Attach manually with: tmux -L {config.socket} attach -t {config.session}"
            )
        else:
            print("\nTmux sessions ready. Attach manually:")
            print(f"  tmux -L {config.socket} attach -t {config.planner_session}")
            print(f"  tmux -L {config.socket} attach -t {config.executer_session}")
        return

    if layout == "split":
        print("\nAttaching to tmux... (detach with Ctrl-b then d)")
        result = run_tmux_command(
            tmux_socket_args(config.socket) + ["attach", "-t", config.session],
            check=False,
            capture=False,
            desc="attach",
        )
        if isinstance(result, subprocess.CompletedProcess) and result.returncode != 0:
            print(
                f"⚠️  tmux attach failed. Run manually: tmux -L {config.socket} attach -t {config.session}"
            )
        return

    if sys.platform == "darwin":
        preferred = os.environ.get("POLI_TERMINAL", "auto").lower()
        socket = config.socket
        planner = config.planner_session
        executer = config.executer_session

        def try_iterm() -> bool:
            iterm_script = f"""
tell application "iTerm"
  set win1 to (create window with default profile)
  tell current session of win1 to write text "tmux -L {socket} attach -t {planner}"
  delay 0.2
  set win2 to (create window with default profile)
  tell current session of win2 to write text "tmux -L {socket} attach -t {executer}"
  activate
end tell
"""
            try:
                subprocess.run(["osascript"], input=iterm_script, text=True, check=True)
                print("\niTerm windows opened for PLANNER and EXECUTER.")
                return True
            except subprocess.CalledProcessError:
                return False

        def try_terminal() -> bool:
            term_script = f"""
tell application "Terminal"
  do script "tmux -L {socket} attach -t {planner}"
  delay 0.2
  do script "tmux -L {socket} attach -t {executer}"
  activate
end tell
"""
            try:
                subprocess.run(["osascript"], input=term_script, text=True, check=True)
                print("\nTerminal.app windows opened for PLANNER and EXECUTER.")
                return True
            except subprocess.CalledProcessError:
                return False

        used = False
        if preferred in ("auto", "iterm"):
            used = try_iterm()
        if not used and preferred in ("auto", "terminal"):
            used = try_terminal()
        if used:
            print("Detach with Ctrl-b then d if needed; tmux UI is minimized.")
            return
        else:
            print("⚠️  Failed to open macOS terminal windows. Falling back to manual instructions.")

    print("\nTmux sessions ready. Attach manually:")
    print(f"  tmux -L {config.socket} attach -t {config.planner_session}")
    print(f"  tmux -L {config.socket} attach -t {config.executer_session}")


def prompt_with_default(message: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{message}{suffix}: ").strip()
    return value or (default or "")


def choose_command_cli(
    role: str,
    options: List[Tuple[str, str]],
    previous_cmd: Optional[str],
) -> str:
    option_map: Dict[str, str] = {}
    print(f"\n{role} command")
    for idx, (label, command) in enumerate(options, start=1):
        option_map[str(idx)] = command
        print(f"  {idx}. {command}")
    custom_index = str(len(options) + 1)
    print(f"  {custom_index}. {CUSTOM_LABEL}")

    default_choice = custom_index
    if previous_cmd:
        for key, command in option_map.items():
            if command.strip() == previous_cmd.strip():
                default_choice = key
                break

    choice = prompt_with_default("Choice", default_choice)
    if choice == custom_index:
        default_cmd = previous_cmd or ""
        custom_value = prompt_with_default("Custom command", default_cmd)
        if not custom_value:
            raise ValueError(f"{role} command cannot be empty")
        return custom_value

    if choice not in option_map:
        raise ValueError("Invalid choice")
    return option_map[choice]


def run_cli_flow(
    previous: Optional[SessionConfig],
    prefs: Dict[str, object],
) -> Tuple[Optional[SessionConfig], bool, bool, str]:
    print("=" * 60)
    print("PoliTerm Session Wizard (CLI)")
    print("=" * 60)

    prev_planner = previous.planner_cmd if previous else None
    prev_executer = previous.executer_cmd if previous else None

    planner_cmd = choose_command_cli("Planner", PLANNER_MODES, prev_planner)
    executer_cmd = choose_command_cli("Executer", EXECUTER_MODES, prev_executer)

    default_dir = previous.project_dir if previous else Path.cwd()
    project_dir = Path(
        prompt_with_default("Working directory", str(default_dir))
    ).expanduser().resolve()

    if not project_dir.exists():
        answer = prompt_with_default(f"Create {project_dir}?", "y").lower()
        if answer in ("y", "yes", "e"):
            project_dir.mkdir(parents=True, exist_ok=True)
        else:
            print("Cancelled.")
            return None, bool(prefs["debug_tmux"]), bool(prefs["auto_attach"]), str(prefs["layout"])

    debug_choice = prompt_with_default(
        "Log tmux commands?", "y" if prefs["debug_tmux"] else "n"
    ).lower()
    auto_choice = prompt_with_default(
        "Auto attach tmux?",
        "y" if prefs["auto_attach"] else "n",
    ).lower()
    layout_choice = prompt_with_default(
        "Layout (split/windows)", str(prefs["layout"])
    ).lower()
    if layout_choice not in ("split", "windows"):
        layout_choice = str(prefs["layout"])

    config = SessionConfig(
        project_dir=project_dir,
        planner_cmd=planner_cmd,
        executer_cmd=executer_cmd,
        socket=DEFAULT_SOCKET,
        session=DEFAULT_SESSION,
    )

    print("\nSummary:")
    print(f"  Working directory : {config.project_dir}")
    print(f"  Planner command : {config.planner_cmd}")
    print(f"  Executer command : {config.executer_cmd}")
    print(f"  tmux socket     : {config.socket}")
    print(f"  tmux session    : {config.session}")
    print(f"  planner session : {config.planner_session}")
    print(f"  executer session: {config.executer_session}")

    confirm = prompt_with_default("Proceed?", "y").lower()
    if confirm == "n":
        print("Cancelled.")
        return None, bool(prefs["debug_tmux"]), bool(prefs["auto_attach"]), str(prefs["layout"])

    return (
        config,
        debug_choice not in ("n", "no", "h"),
        auto_choice not in ("n", "no", "h"),
        layout_choice,
    )


def resolve_mode(command: Optional[str], options: List[Tuple[str, str]]) -> Tuple[str, str]:
    if command:
        cmd_clean = command.strip()
        for label, preset in options:
            if preset.strip() == cmd_clean:
                return label, ""
        return CUSTOM_LABEL, cmd_clean
    return options[0][0], ""


def build_command(mode: str, custom_value: str, options: Dict[str, str]) -> str:
    if mode == CUSTOM_LABEL:
        return custom_value.strip()
    return options.get(mode, "").strip()


def launch_gui(
    previous: Optional[SessionConfig],
    prefs: Dict[str, object],
) -> Tuple[Optional[SessionConfig], bool, bool, str]:
    if tk is None or ttk is None or filedialog is None:
        return None, bool(prefs["debug_tmux"]), bool(prefs["auto_attach"]), str(prefs["layout"])

    root = tk.Tk()
    root.title("PoliTerm Session Wizard")
    root.geometry("700x540")
    root.minsize(660, 480)

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    planner_map = {label: cmd for label, cmd in PLANNER_MODES}
    executer_map = {label: cmd for label, cmd in EXECUTER_MODES}

    planner_mode_default, planner_custom_default = resolve_mode(
        previous.planner_cmd if previous else None, PLANNER_MODES
    )
    executer_mode_default, executer_custom_default = resolve_mode(
        previous.executer_cmd if previous else None, EXECUTER_MODES
    )

    dir_var = tk.StringVar(value=str(previous.project_dir if previous else Path.cwd()))
    planner_mode_var = tk.StringVar(value=planner_mode_default)
    planner_custom_var = tk.StringVar(value=planner_custom_default)
    planner_command_var = tk.StringVar()
    executer_mode_var = tk.StringVar(value=executer_mode_default)
    executer_custom_var = tk.StringVar(value=executer_custom_default)
    executer_command_var = tk.StringVar()
    debug_var = tk.BooleanVar(value=bool(prefs["debug_tmux"]))
    attach_var = tk.BooleanVar(value=bool(prefs["auto_attach"]))
    layout_default = str(prefs["layout"]) if str(prefs["layout"]) in ("split", "windows") else "split"

    result: Dict[str, object] = {
        "config": None,
        "debug": bool(prefs["debug_tmux"]),
        "attach": bool(prefs["auto_attach"]),
        "layout": layout_default,
    }

    main_frame = ttk.Frame(root, padding=16)
    main_frame.pack(fill="both", expand=True)
    for col in range(3):
        main_frame.columnconfigure(col, weight=1)
    main_frame.rowconfigure(11, weight=1)

    ttk.Label(main_frame, text="Working directory").grid(row=0, column=0, sticky="w")
    dir_entry = ttk.Entry(main_frame, textvariable=dir_var, width=50)
    dir_entry.grid(row=1, column=0, columnspan=2, sticky="we", pady=(2, 8))
    ttk.Button(
        main_frame,
        text="Browse",
        width=12,
        command=lambda: browse_directory(dir_var),
    ).grid(row=1, column=2, sticky="e")

    ttk.Label(main_frame, text="Planner mode").grid(row=2, column=0, sticky="w")
    planner_combo = ttk.Combobox(
        main_frame,
        state="readonly",
        values=[label for label, _ in PLANNER_MODES] + [CUSTOM_LABEL],
        textvariable=planner_mode_var,
    )
    planner_combo.grid(row=3, column=0, columnspan=3, sticky="we")
    planner_custom_entry = ttk.Entry(main_frame, textvariable=planner_custom_var, width=50)
    planner_custom_entry.grid(row=4, column=0, columnspan=3, sticky="we", pady=(2, 6))
    planner_command_label = ttk.Label(main_frame, text="Command: ")
    planner_command_label.grid(row=5, column=0, columnspan=3, sticky="w")

    ttk.Label(main_frame, text="Executer mode").grid(row=6, column=0, sticky="w", pady=(10, 0))
    executer_combo = ttk.Combobox(
        main_frame,
        state="readonly",
        values=[label for label, _ in EXECUTER_MODES] + [CUSTOM_LABEL],
        textvariable=executer_mode_var,
    )
    executer_combo.grid(row=7, column=0, columnspan=3, sticky="we")
    executer_custom_entry = ttk.Entry(main_frame, textvariable=executer_custom_var, width=50)
    executer_custom_entry.grid(row=8, column=0, columnspan=3, sticky="we", pady=(2, 6))
    executer_command_label = ttk.Label(main_frame, text="Command: ")
    executer_command_label.grid(row=9, column=0, columnspan=3, sticky="w")

    options_frame = ttk.LabelFrame(main_frame, text="Options")
    options_frame.grid(row=10, column=0, columnspan=3, pady=(12, 0), sticky="we")
    options_frame.columnconfigure(0, weight=1)
    ttk.Checkbutton(options_frame, text="Log tmux commands", variable=debug_var).grid(
        row=0, column=0, sticky="w", padx=8, pady=(4, 2)
    )
    ttk.Checkbutton(options_frame, text="Auto attach tmux", variable=attach_var).grid(
        row=1, column=0, sticky="w", padx=8, pady=(0, 6)
    )

    layout_frame = ttk.LabelFrame(main_frame, text="Layout")
    layout_frame.grid(row=11, column=0, columnspan=3, pady=(12, 0), sticky="we")
    layout_frame.columnconfigure(0, weight=1)
    layout_var = tk.StringVar(value=layout_default)
    ttk.Radiobutton(
        layout_frame,
        text="Split panes (one window)",
        value="split",
        variable=layout_var,
    ).grid(row=0, column=0, sticky="w", padx=8, pady=(4, 2))
    ttk.Radiobutton(
        layout_frame,
        text="Separate windows",
        value="windows",
        variable=layout_var,
    ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 6))

    buttons = ttk.Frame(main_frame)
    buttons.grid(row=12, column=0, columnspan=3, pady=(18, 0), sticky="e")
    ttk.Button(buttons, text="Cancel", command=root.destroy).pack(side="right", padx=(0, 8))

    def on_start() -> None:
        project_path = Path(dir_var.get().strip()).expanduser()
        if not project_path.exists():
            if not messagebox.askyesno("Create directory", f"Create {project_path}?"):
                return
            try:
                project_path.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                messagebox.showerror("Error", f"Failed to create directory:\n{exc}")
                return

        planner_command = build_command(
            planner_mode_var.get(), planner_custom_var.get(), planner_map
        )
        executer_command = build_command(
            executer_mode_var.get(), executer_custom_var.get(), executer_map
        )

        if not planner_command:
            messagebox.showerror("Error", "Planner command cannot be empty")
            return
        if not executer_command:
            messagebox.showerror("Error", "Executer command cannot be empty")
            return

        result["config"] = SessionConfig(
            project_dir=project_path,
            planner_cmd=planner_command,
            executer_cmd=executer_command,
            socket=DEFAULT_SOCKET,
            session=DEFAULT_SESSION,
        )
        result["debug"] = bool(debug_var.get())
        result["attach"] = bool(attach_var.get())
        result["layout"] = layout_var.get()
        root.destroy()

    ttk.Button(buttons, text="Start", command=on_start).pack(side="right")

    def refresh_planner_state(*_: object) -> None:
        is_custom = planner_mode_var.get() == CUSTOM_LABEL
        planner_custom_entry.configure(state="normal" if is_custom else "disabled")
        planner_command = build_command(
            planner_mode_var.get(), planner_custom_var.get(), planner_map
        )
        planner_command_var.set(planner_command)
        planner_command_label.configure(text=f"Command: {planner_command or '-'}")

    def refresh_executer_state(*_: object) -> None:
        is_custom = executer_mode_var.get() == CUSTOM_LABEL
        executer_custom_entry.configure(state="normal" if is_custom else "disabled")
        executer_command = build_command(
            executer_mode_var.get(), executer_custom_var.get(), executer_map
        )
        executer_command_var.set(executer_command)
        executer_command_label.configure(text=f"Command: {executer_command or '-'}")

    def browse_directory(var: tk.StringVar) -> None:
        initial = var.get() or str(Path.cwd())
        selected = filedialog.askdirectory(initialdir=initial)
        if selected:
            var.set(selected)

    planner_mode_var.trace_add("write", refresh_planner_state)
    planner_custom_var.trace_add("write", refresh_planner_state)
    executer_mode_var.trace_add("write", refresh_executer_state)
    executer_custom_var.trace_add("write", refresh_executer_state)

    refresh_planner_state()
    refresh_executer_state()

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()

    return (
        result["config"],
        bool(result["debug"]),
        bool(result["attach"]),
        str(result["layout"]),
    )


def load_primer_lines(kind: str) -> List[str]:
    candidates = [
        CONFIG_DIR / f"{kind}_primer_v3.txt",
        CONFIG_DIR / f"{kind}_primer_v2.txt",
        CONFIG_DIR / f"{kind}_primer.txt",
    ]
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8").splitlines()
    if kind == "planner":
        return [
            "You are PLANNER. Coordinate with the user until they instruct you to hand off a plan to EXECUTER.",
            "When you are ready, emit a POLI:MSG block to EXECUTER following the documented contract.",
        ]
    return [
        "You are EXECUTER. Wait for plans from PLANNER and respond with STATUS and RESULT blocks as required.",
    ]


def orchestrate(
    config: SessionConfig,
    debug_tmux: bool,
    auto_attach: bool,
    layout: str,
) -> None:
    config.project_dir.mkdir(parents=True, exist_ok=True)
    kill_existing_sessions(config)
    start_tmux_topology(config, layout)
    # Optional: enable tmux pane logging as early as panes exist
    if PANE_LOG:
        try:
            args = tmux_socket_args(config.socket)
            if layout == "split":
                planner_target = f"{config.session}.0"
                executer_target = f"{config.session}.1"
            else:
                planner_target = f"{config.planner_session}:{config.window_name}.0"
                executer_target = f"{config.executer_session}:{config.window_name}.0"
            LOG_DIR.mkdir(exist_ok=True)
            # choose logging command: prefer 'ts' if available, else plain cat
            has_ts = shutil.which("ts") is not None
            cmd_p = (f"ts >> {str(LOG_DIR / 'planner_pane.log')}" if has_ts else f">> {str(LOG_DIR / 'planner_pane.log')} cat")
            cmd_e = (f"ts >> {str(LOG_DIR / 'executer_pane.log')}" if has_ts else f">> {str(LOG_DIR / 'executer_pane.log')} cat")
            run_tmux_command(
                args + ["pipe-pane", "-o", "-t", planner_target, cmd_p],
                check=False,
                capture=False,
                desc="log:planner:on",
            )
            run_tmux_command(
                args + ["pipe-pane", "-o", "-t", executer_target, cmd_e],
                check=False,
                capture=False,
                desc="log:executer:on",
            )
        except Exception:
            pass
    if PRIMER_DELAY > 0:
        print(f"Waiting {PRIMER_DELAY:.1f}s for TUIs to start...")
        time.sleep(PRIMER_DELAY)

    # Heuristic readiness checks to avoid racing with CLI self-initialization
    def wait_ready(target: str, patterns: List[str], timeout: float = READY_TIMEOUT) -> None:
        start = time.time()
        args = tmux_socket_args(config.socket)
        last = None
        last_change = time.time()
        while time.time() - start < timeout:
            out = run_tmux_command(
                args + ["capture-pane", "-t", target, "-pJS", "-120"],
                check=False,
                capture=True,
            ).stdout or ""
            if out != last:
                last = out
                last_change = time.time()

            has_prompt = any(pat in out for pat in patterns)
            looks_idle = (
                (">" in out.splitlines()[-1:][0] if out.splitlines() else False)
                and ("Wandering" not in out)
            )
            if has_prompt and looks_idle and (time.time() - last_change) >= READY_IDLE:
                return
            time.sleep(0.2)

    try:
        print("Checking PLANNER readiness...")
        wait_ready(
            f"{config.planner_session}:{config.window_name}.0" if layout != "split" else f"{config.session}.0",
            patterns=["Welcome to Claude Code", "? for shortcuts", "cwd:"],
            timeout=READY_TIMEOUT,
        )
    except Exception:
        pass

    try:
        print("Checking EXECUTER readiness...")
        wait_ready(
            f"{config.executer_session}:{config.window_name}.0" if layout != "split" else f"{config.session}.1",
            patterns=["OpenAI Codex", "directory:"],
            timeout=READY_TIMEOUT,
        )
    except Exception:
        pass
    planner_lines = load_primer_lines("planner")
    executer_lines = load_primer_lines("executer")
    print("Injecting primers...")
    if layout == "split":
        planner_target = f"{config.session}.0"
        executer_target = f"{config.session}.1"
    else:
        planner_target = f"{config.planner_session}:{config.window_name}.0"
        executer_target = f"{config.executer_session}:{config.window_name}.0"

    send_lines_to_target(config, planner_target, planner_lines)
    send_lines_to_target(config, executer_target, executer_lines)
    persist_session(config, debug_tmux, auto_attach, layout)
    attach_tmux_sessions(config, auto_attach, layout)
    if layout == "split":
        followup = "  - Continue working with the PLANNER pane.\n"
    else:
        followup = (
            "  - Keep both PLANNER and EXECUTER windows handy for the continuous loop.\n"
        )
    print(
        "\nReady! After detaching from tmux:\n"
        + followup
        + "  - Bridge the loop with: python3 proto/poli_orchestrator_v3.py --monitor"
    )


def main() -> int:
    global DEBUG_TMUX, AUTO_ATTACH

    parser = argparse.ArgumentParser(description="PoliTerm session wizard")
    parser.add_argument("--cli", action="store_true", help="Force text-based wizard")
    parser.add_argument("--no-attach", action="store_true", help="Do not auto-attach tmux")
    parser.add_argument("--debug-tmux", action="store_true", help="Force tmux command logging")
    parser.add_argument("--no-debug", action="store_true", help="Disable tmux command logging")
    parser.add_argument("--primer-delay", type=float, help="Delay before primer injection (seconds)")

    args = parser.parse_args()

    if getattr(args, "debug_tmux", False):
        DEBUG_TMUX = True
    if args.no_debug:
        DEBUG_TMUX = False
    if args.no_attach:
        AUTO_ATTACH = False
    if args.primer_delay is not None and args.primer_delay >= 0:
        global PRIMER_DELAY
        PRIMER_DELAY = float(args.primer_delay)

    previous, prefs = load_previous_session()

    config: Optional[SessionConfig]
    debug_choice: bool
    attach_choice: bool
    layout_choice: str

    if args.cli or tk is None or ttk is None:
        if not args.cli and tk is None:
            print(
                "tkinter missing (_tkinter not found); falling back to CLI.\n"
                "macOS tip: brew install python-tk@3.13 (or matching version),\n"
                "or try python3 -m pip install tk."
            )
        try:
            config, debug_choice, attach_choice, layout_choice = run_cli_flow(previous, prefs)
        except ValueError as exc:
            print(f"Error: {exc}")
            return 1
        if config is None:
            return 1
    else:
        config, debug_choice, attach_choice, layout_choice = launch_gui(previous, prefs)
        if config is None:
            print("Cancelled.")
            return 1

    DEBUG_TMUX = debug_choice
    AUTO_ATTACH = attach_choice

    try:
        orchestrate(config, DEBUG_TMUX, AUTO_ATTACH, layout_choice)
    except KeyboardInterrupt:
        print("\nCancelled.")
        return 1
    except Exception as exc:
        print(f"\nError: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
