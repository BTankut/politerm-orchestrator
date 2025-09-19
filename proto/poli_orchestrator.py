#!/usr/bin/env python3
"""
PoliTerm Orchestrator Engine
Coordinates communication between PLANNER and EXECUTER TUIs via tmux
"""

import json
import re
import subprocess
import time
import uuid
import os
import sys
import logging
from typing import Optional, Tuple, Dict, List, Set
from dataclasses import dataclass
from enum import Enum

# Configuration from environment
SOCKET = os.environ.get("POLI_TMUX_SOCKET", "poli")
SESSION = os.environ.get("POLI_TMUX_SESSION", "main")
PLANNER_PANE = f"{SESSION}.0"
EXECUTER_PANE = f"{SESSION}.1"

PLAN_TIMEOUT = float(os.environ.get("POLI_PLAN_TIMEOUT", "180"))
EXEC_TIMEOUT = float(os.environ.get("POLI_EXEC_TIMEOUT", "900"))
POLL_INTERVAL = float(os.environ.get("POLI_POLL_INTERVAL", "0.4"))
CAPTURE_LINES = int(os.environ.get("POLI_CAPTURE_LINES", "400"))

# Logging configuration
LOG_LEVEL = os.environ.get("POLI_LOG_LEVEL", "INFO")
LOG_FILE = os.environ.get("POLI_LOG_FILE", "")

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("poli_orchestrator")

if LOG_FILE:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(file_handler)

# tmux command base
TMUX = ["tmux", "-L", SOCKET]


class MessageType(Enum):
    """Types of messages in the POLI protocol"""
    PLAN = "plan"
    RESULT = "result"
    STATUS = "status"
    ERROR = "error"


@dataclass
class PoliMessage:
    """Represents a POLI protocol message"""
    to: str
    type: str
    id: str
    body: str
    raw_meta: Dict


def sh(args: List[str], check: bool = True) -> str:
    """Execute shell command and return output"""
    logger.debug(f"Executing: {' '.join(args)}")
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            check=check
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e}")
        if check:
            raise
        return e.stdout


def tmux_exists() -> bool:
    """Check if tmux session exists"""
    try:
        sh(TMUX + ["has-session", "-t", SESSION], check=True)
        return True
    except subprocess.CalledProcessError:
        return False


def send_keys(target: str, text: str, with_enter: bool = True) -> None:
    """Send text to tmux pane, preserving newlines"""
    logger.info(f"Sending to {target}: {text[:100]}{'...' if len(text) > 100 else ''}")

    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line:  # Send non-empty lines
            sh(TMUX + ["send-keys", "-t", target, line])
        # Send Enter after each line except potentially the last
        if with_enter and (i < len(lines) - 1 or i == len(lines) - 1):
            sh(TMUX + ["send-keys", "-t", target, "C-m"])


def capture_tail(target: str, lines: int = None) -> str:
    """Capture the tail of a tmux pane"""
    if lines is None:
        lines = CAPTURE_LINES

    # -p = print pane, -J = join wrapped lines, -S = start line (negative from end)
    output = sh(TMUX + ["capture-pane", "-t", target, "-pJS", f"-{lines}"])
    logger.debug(f"Captured {len(output)} chars from {target}")
    return output


# Regex for parsing POLI message blocks
BLOCK_RE = re.compile(
    r"\[\[POLI:MSG\s+(\{.*?\})\]\](.*?)\[\[/POLI:MSG\]\]",
    re.DOTALL | re.MULTILINE
)


def find_blocks(buffer: str) -> List[PoliMessage]:
    """Find all POLI message blocks in buffer"""
    blocks = []
    for match in BLOCK_RE.finditer(buffer):
        try:
            meta_str = match.group(1)
            body = match.group(2).strip()
            meta = json.loads(meta_str)

            msg = PoliMessage(
                to=meta.get("to", ""),
                type=meta.get("type", ""),
                id=str(meta.get("id", "")),
                body=body,
                raw_meta=meta
            )
            blocks.append(msg)
            logger.debug(f"Found block: to={msg.to}, type={msg.type}, id={msg.id}")
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse block: {e}")

    return blocks


def wait_for_new_block(
    target: str,
    seen_ids: Set[str],
    timeout: float = 120.0,
    expected_type: Optional[str] = None
) -> Optional[PoliMessage]:
    """Wait for a new message block from target pane"""
    logger.info(f"Waiting for new block from {target} (timeout={timeout}s)")

    start_time = time.time()
    last_nudge_time = start_time
    nudge_interval = timeout / 3  # Nudge at 1/3 and 2/3 of timeout

    while time.time() - start_time < timeout:
        buffer = capture_tail(target)
        blocks = find_blocks(buffer)

        for msg in blocks:
            if msg.id and msg.id not in seen_ids:
                if expected_type and msg.type != expected_type:
                    logger.debug(f"Skipping block with type {msg.type} (expected {expected_type})")
                    continue
                logger.info(f"Found new block: {msg.id} (type={msg.type})")
                return msg

        # Send nudge if we're getting close to timeout
        if time.time() - last_nudge_time > nudge_interval:
            logger.info(f"Sending nudge to {target}")
            send_keys(
                target,
                "\n# Reminder: Please emit your tagged response block if you're finished.\n",
                with_enter=True
            )
            last_nudge_time = time.time()

        time.sleep(POLL_INTERVAL)

    logger.warning(f"Timeout waiting for block from {target}")
    return None


def route_once(user_prompt: str, task_id: Optional[str] = None) -> bool:
    """Execute one complete routing cycle: User → Planner → Executer → Planner"""

    if not task_id:
        task_id = str(uuid.uuid4())

    logger.info(f"Starting route cycle with task_id={task_id}")
    print(f"\n{'='*60}")
    print(f"Task ID: {task_id}")
    print(f"{'='*60}\n")

    # Track seen message IDs
    seen_ids: Set[str] = set()

    # Step 1: Send user request to PLANNER
    planner_prompt = f"""TASK_ID={task_id}

User request:
{user_prompt}

Please analyze this request and produce exactly one tagged block addressed to EXECUTER with id={task_id}.
Remember to use the POLI:MSG format as specified in your primer."""

    print(f"📤 Sending request to PLANNER...")
    send_keys(PLANNER_PANE, planner_prompt)

    # Step 2: Wait for PLANNER to emit plan block
    print(f"⏳ Waiting for PLANNER to create plan...")
    plan_msg = wait_for_new_block(
        PLANNER_PANE,
        seen_ids,
        timeout=PLAN_TIMEOUT,
        expected_type="plan"
    )

    if not plan_msg:
        print("❌ PLANNER did not produce a plan in time")
        logger.error("Failed to get plan from PLANNER")
        return False

    seen_ids.add(plan_msg.id)
    print(f"✅ Received plan from PLANNER")

    # Step 3: Forward plan to EXECUTER
    executer_prompt = f"""You received a plan from PLANNER:

[[POLI:MSG {json.dumps(plan_msg.raw_meta)}]]
{plan_msg.body}
[[/POLI:MSG]]

Please execute this plan step by step.
When complete, emit a RESULT block back to PLANNER with id={task_id}.
You may emit optional STATUS blocks during execution."""

    print(f"📤 Forwarding plan to EXECUTER...")
    send_keys(EXECUTER_PANE, executer_prompt)

    # Step 4: Wait for EXECUTER to complete and emit result
    print(f"⏳ Waiting for EXECUTER to complete task...")

    # Also look for status updates
    exec_start = time.time()
    result_msg = None

    while time.time() - exec_start < EXEC_TIMEOUT:
        buffer = capture_tail(EXECUTER_PANE)
        blocks = find_blocks(buffer)

        for msg in blocks:
            if msg.id not in seen_ids:
                seen_ids.add(msg.id)

                if msg.type == "status":
                    print(f"📊 Status update from EXECUTER: {msg.body[:100]}...")
                    logger.info(f"Status from EXECUTER: {msg.body}")
                elif msg.type == "result":
                    result_msg = msg
                    break

        if result_msg:
            break

        time.sleep(POLL_INTERVAL)

    if not result_msg:
        print("❌ EXECUTER did not complete in time")
        logger.error("Failed to get result from EXECUTER")
        return False

    print(f"✅ Received result from EXECUTER")

    # Step 5: Send result back to PLANNER for final summary
    summary_prompt = f"""EXECUTER has completed the task and replied:

[[POLI:MSG {json.dumps(result_msg.raw_meta)}]]
{result_msg.body}
[[/POLI:MSG]]

Please provide a concise final summary for the user about what was accomplished.
Do not emit any new POLI:MSG blocks, just provide a natural language summary."""

    print(f"📤 Sending result back to PLANNER for summary...")
    send_keys(PLANNER_PANE, summary_prompt)

    # Give PLANNER a moment to generate summary
    time.sleep(2)

    print(f"\n{'='*60}")
    print(f"✅ Route cycle completed successfully!")
    print(f"{'='*60}\n")

    return True


def interactive_mode():
    """Run orchestrator in interactive mode"""
    print("\n" + "="*60)
    print("PoliTerm Orchestrator - Interactive Mode")
    print("="*60)
    print("\nType 'exit' or 'quit' to stop")
    print("Type 'status' to check tmux session")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("\n💭 Enter task for PLANNER (or command): ").strip()

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("Exiting...")
                break

            if user_input.lower() == 'status':
                if tmux_exists():
                    print("✅ tmux session is running")
                    output = sh(TMUX + ["list-panes", "-t", SESSION], check=False)
                    print(output)
                else:
                    print("❌ tmux session not found")
                continue

            if not user_input:
                continue

            if not tmux_exists():
                print("❌ Error: tmux session not found. Run: bash scripts/bootstrap_tmux.sh")
                continue

            success = route_once(user_input)

            if success:
                print("✨ Task completed successfully!")
            else:
                print("⚠️ Task failed or timed out")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in interactive mode: {e}", exc_info=True)
            print(f"❌ Error: {e}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="PoliTerm Orchestrator")
    parser.add_argument(
        "--task", "-t",
        help="Single task to execute (non-interactive mode)"
    )
    parser.add_argument(
        "--task-id",
        help="Specific task ID to use"
    )
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Check if tmux session exists"
    )

    args = parser.parse_args()

    if args.check:
        if tmux_exists():
            print("✅ tmux session is running")
            sys.exit(0)
        else:
            print("❌ tmux session not found")
            sys.exit(1)

    if not tmux_exists():
        print("❌ Error: tmux session not found")
        print("\nPlease run: bash scripts/bootstrap_tmux.sh")
        sys.exit(1)

    if args.task:
        # Single task mode
        success = route_once(args.task, args.task_id)
        sys.exit(0 if success else 1)
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()