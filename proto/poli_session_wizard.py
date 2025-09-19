#!/usr/bin/env python3
"""Interactive setup wizard for PoliTerm continuous dialogue sessions."""
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
# Repo root is two levels up from this file
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
CONFIG_DIR = REPO_ROOT / "config"
LOG_DIR = REPO_ROOT / "logs"
DEFAULT_SOCKET = os.environ.get("POLI_TMUX_SOCKET", "poli")
DEFAULT_SESSION = os.environ.get("POLI_TMUX_SESSION", "main")
SESSION_STATE_FILE = CONFIG_DIR / "last_session.json"
@dataclass
class SessionConfig:
    project_dir: Path
    planner_cmd: str
    executer_cmd: str
    socket: str = DEFAULT_SOCKET
    session: str = DEFAULT_SESSION
    @property
    def planner_cwd(self) -> Path:
        return self.project_dir
    @property
    def executer_cwd(self) -> Path:
        return self.project_dir
def prompt_with_default(message: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{message}{suffix}: ").strip()
    return value or (default or "")
def choose_project_dir(previous: Optional[Path] = None) -> Path:
    default_dir = previous or Path.cwd()
    while True:
        raw = prompt_with_default("Çalışma klasörü", str(default_dir))
        path = Path(raw).expanduser().resolve()
        if path.exists():
            return path
        create = input(f"{path} mevcut değil. Oluşturulsun mu? [y/N]: ").strip().lower()
        if create == "y":
            path.mkdir(parents=True, exist_ok=True)
            return path
def choose_cli_commands(previous: Optional[SessionConfig] = None) -> SessionConfig:
    presets = {
        "1": ("claude", "codex", "Claude (planner) + Codex (executer)"),
        "2": ("claude", "claude", "Double Claude"),
    }
    print("\nPlanner/Executer CLI seçimi:")
    for key, (_, _, label) in presets.items():
        print(f"  {key}. {label}")
    print("  3. Özel komutlar")
    default_choice = ""
    if previous:
        for key, (plan_cmd, exec_cmd, _) in presets.items():
            if plan_cmd == previous.planner_cmd and exec_cmd == previous.executer_cmd:
                default_choice = key
                break
        else:
            default_choice = "3"
    choice = prompt_with_default("Seçiminiz", default_choice or "1")
    if choice in presets:
        planner_cmd, executer_cmd, label = presets[choice]
        print(f"→ {label} seçildi")
    else:
        planner_cmd = prompt_with_default("Planner komutu", previous.planner_cmd if previous else "claude")
        executer_cmd = prompt_with_default("Executer komutu", previous.executer_cmd if previous else "codex")
    return SessionConfig(
        project_dir=Path(),  # placeholder; güncel değer daha sonra atanacak
        planner_cmd=planner_cmd,
        executer_cmd=executer_cmd,
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
def run_tmux_command(args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, text=True, capture_output=False, check=check)
def tmux_socket_args(socket: str) -> List[str]:
    return ["tmux", "-L", socket]

def kill_existing_session(config: SessionConfig) -> None:
    try:
        run_tmux_command(tmux_socket_args(config.socket) + ["has-session", "-t", config.session])
    except subprocess.CalledProcessError:
        return
    print(f"\n⚠️  '{config.session}' oturumu zaten açık. Kapatılıyor...")
    run_tmux_command(["bash", str(REPO_ROOT / "scripts" / "kill_tmux.sh")], check=False)
    time.sleep(0.5)


def attach_tmux_session(config: SessionConfig) -> None:
    """Attach to the newly created tmux session"""
    print("\nTmux oturumu açılıyor... (ayrılmak için Ctrl-b ardından d)")
    result = run_tmux_command(
        tmux_socket_args(config.socket) + ["attach", "-t", config.session],
        check=False
    )
    if isinstance(result, subprocess.CompletedProcess) and result.returncode != 0:
        print(f"⚠️  tmux attach başarısız. Elle çalıştırın: tmux -L {config.socket} attach -t {config.session}")


def start_tmux_session(config: SessionConfig) -> None:
    args = tmux_socket_args(config.socket)

    run_tmux_command(args + [
        "-f", "/dev/null",
        "new-session",
        "-d",
        "-s",
        config.session,
        "-c",
        str(config.planner_cwd),
    ])

    run_tmux_command(args + ["send-keys", "-t", f"{config.session}.0", config.planner_cmd, "C-m"])

    run_tmux_command(args + [
        "split-window",
        "-h",
        "-t",
        config.session,
        "-c",
        str(config.executer_cwd),
    ])

    run_tmux_command(args + ["send-keys", "-t", f"{config.session}.1", config.executer_cmd, "C-m"])

    time.sleep(2.0)


def send_lines_to_pane(config: SessionConfig, pane_index: int, lines: List[str]) -> None:
    args = tmux_socket_args(config.socket)
    target = f"{config.session}.{pane_index}"
    for line in lines:
        if line:
            run_tmux_command(args + ["send-keys", "-t", target, line])
        run_tmux_command(args + ["send-keys", "-t", target, "C-m"])
        time.sleep(0.05)
def persist_session(config: SessionConfig) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    CONFIG_DIR.mkdir(exist_ok=True)
    data = {
        "project_dir": str(config.project_dir),
        "planner_cmd": config.planner_cmd,
        "executer_cmd": config.executer_cmd,
        "socket": config.socket,
        "session": config.session,
        "saved_at": time.time(),
    }
    SESSION_STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
def load_previous_session() -> Optional[SessionConfig]:
    if not SESSION_STATE_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_STATE_FILE.read_text(encoding="utf-8"))
        return SessionConfig(
            project_dir=Path(data["project_dir"]).expanduser(),
            planner_cmd=data["planner_cmd"],
            executer_cmd=data["executer_cmd"],
            socket=data.get("socket", DEFAULT_SOCKET),
            session=data.get("session", DEFAULT_SESSION),
        )
    except Exception:
        return None
def main() -> int:
    print("=" * 60)
    print("PoliTerm Başlangıç Sihirbazı")
    print("=" * 60)
    previous = load_previous_session()
    temp_config = choose_cli_commands(previous)
    project_dir = choose_project_dir(previous.project_dir if previous else None)
    config = SessionConfig(
        project_dir=project_dir,
        planner_cmd=temp_config.planner_cmd,
        executer_cmd=temp_config.executer_cmd,
        socket=DEFAULT_SOCKET,
        session=DEFAULT_SESSION,
    )
    print("\nÖzet:")
    print(f"  Çalışma klasörü : {config.project_dir}")
    print(f"  Planner komutu  : {config.planner_cmd}")
    print(f"  Executer komutu : {config.executer_cmd}")
    print(f"  tmux socket     : {config.socket}")
    print(f"  tmux oturumu    : {config.session}")
    confirm = input("Devam edilsin mi? [Y/n]: ").strip().lower()
    if confirm == "n":
        print("İptal edildi.")
        return 1
    config.project_dir.mkdir(parents=True, exist_ok=True)
    kill_existing_session(config)
    start_tmux_session(config)
    planner_lines = load_primer_lines("planner")
    executer_lines = load_primer_lines("executer")
    print("Roller yükleniyor...")
    send_lines_to_pane(config, 0, planner_lines)
    send_lines_to_pane(config, 1, executer_lines)
    persist_session(config)
    attach_tmux_session(config)
    print("\nHazır! tmux'tan ayrıldıktan sonra:")
    print("  - PLANNER ile konuşmaya devam edebilirsiniz.")
    print("  - Gerekirse orchestrator'ı çalıştırmak için yeni bir terminalde: python3 proto/poli_orchestrator_v3.py --monitor")
    return 0
if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nİptal edildi.")
        sys.exit(1)
