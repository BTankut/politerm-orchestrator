#!/usr/bin/env python3
"""
PoliTerm Orchestrator Engine V2 - Continuous Dialogue Loop
Implements full Planner ⇄ Executer continuous communication
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
logger = logging.getLogger("poli_orchestrator_v2")

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
    COMPLETE = "complete"
    CONTINUE = "continue"
    REVISION = "revision"


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
    expected_types: Optional[List[str]] = None
) -> Optional[PoliMessage]:
    """Wait for a new message block from target pane"""
    logger.info(f"Waiting for new block from {target} (timeout={timeout}s, types={expected_types})")

    start_time = time.time()
    last_nudge_time = start_time
    nudge_interval = timeout / 3  # Nudge at 1/3 and 2/3 of timeout

    while time.time() - start_time < timeout:
        buffer = capture_tail(target)
        blocks = find_blocks(buffer)

        for msg in blocks:
            if msg.id and msg.id not in seen_ids:
                if expected_types and msg.type not in expected_types:
                    logger.debug(f"Skipping block with type {msg.type} (expected {expected_types})")
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


def route_continuous(user_prompt: str, task_id: Optional[str] = None, max_rounds: int = 10) -> bool:
    """
    Execute continuous routing cycles: User → Planner ⇄ Executer → User
    Planner supervises and continues until task is complete
    """

    if not task_id:
        task_id = str(uuid.uuid4())

    logger.info(f"Starting CONTINUOUS route with task_id={task_id}, max_rounds={max_rounds}")
    print(f"\n{'='*60}")
    print(f"🔄 CONTINUOUS DIALOGUE MODE")
    print(f"Task ID: {task_id}")
    print(f"Max Rounds: {max_rounds}")
    print(f"{'='*60}\n")

    # Track seen message IDs
    seen_ids: Set[str] = set()
    round_count = 0
    task_complete = False

    # Step 1: Send initial user request to PLANNER
    initial_prompt = f"""TASK_ID={task_id}

User request:
{user_prompt}

IMPORTANT: You are in CONTINUOUS DIALOGUE mode. You will:
1. Create an initial plan
2. Send it to EXECUTER
3. Review EXECUTER's results
4. Continue sending refinements/next steps until the task is FULLY complete
5. Emit a COMPLETE message when done

Start by analyzing this request and producing your first plan block for EXECUTER.
Use type="plan" for initial plan, type="continue" for subsequent instructions.
When the task is fully complete, emit type="complete" to signal completion."""

    print(f"📤 Sending initial request to PLANNER...")
    send_keys(PLANNER_PANE, initial_prompt)

    # CONTINUOUS LOOP
    while round_count < max_rounds and not task_complete:
        round_count += 1
        print(f"\n--- Round {round_count}/{max_rounds} ---")

        # Wait for PLANNER to emit a block (plan/continue/revision/complete)
        print(f"⏳ Waiting for PLANNER decision...")
        planner_msg = wait_for_new_block(
            PLANNER_PANE,
            seen_ids,
            timeout=PLAN_TIMEOUT,
            expected_types=["plan", "continue", "revision", "complete"]
        )

        if not planner_msg:
            print("❌ PLANNER timeout - no response")
            break

        seen_ids.add(planner_msg.id)

        # Check if PLANNER signals completion
        if planner_msg.type == "complete":
            print(f"✅ PLANNER signals task COMPLETE")
            task_complete = True

            # Send final summary request
            final_prompt = f"""Task has been completed successfully.

Please provide a comprehensive final report for the user about:
1. What was requested
2. What was accomplished
3. Key steps taken
4. Final outcome

Do not emit any new POLI:MSG blocks, just provide a natural language summary."""

            print(f"📤 Requesting final summary from PLANNER...")
            send_keys(PLANNER_PANE, final_prompt)
            time.sleep(3)  # Wait for summary
            break

        # Forward PLANNER's instruction to EXECUTER
        print(f"📤 Forwarding {planner_msg.type} to EXECUTER...")
        executer_prompt = f"""You received a {planner_msg.type} from PLANNER:

[[POLI:MSG {json.dumps(planner_msg.raw_meta)}]]
{planner_msg.body}
[[/POLI:MSG]]

Execute this {"plan" if planner_msg.type == "plan" else "instruction"}.
Emit STATUS blocks during execution.
When done, emit a RESULT block back to PLANNER with id={task_id}-R{round_count}.

If you encounter issues, report them in the RESULT block."""

        send_keys(EXECUTER_PANE, executer_prompt)

        # Wait for EXECUTER's response
        print(f"⏳ Waiting for EXECUTER to complete...")
        exec_start = time.time()
        result_msg = None

        while time.time() - exec_start < EXEC_TIMEOUT:
            buffer = capture_tail(EXECUTER_PANE)
            blocks = find_blocks(buffer)

            for msg in blocks:
                if msg.id not in seen_ids:
                    seen_ids.add(msg.id)

                    if msg.type == "status":
                        print(f"  📊 Status: {msg.body[:80]}...")
                        logger.info(f"Status from EXECUTER: {msg.body}")
                    elif msg.type == "result":
                        result_msg = msg
                        break

            if result_msg:
                break

            time.sleep(POLL_INTERVAL)

        if not result_msg:
            print("❌ EXECUTER timeout - no result")
            break

        print(f"✅ Received result from EXECUTER")

        # Send EXECUTER's result back to PLANNER for review
        review_prompt = f"""EXECUTER has completed round {round_count} and reports:

[[POLI:MSG {json.dumps(result_msg.raw_meta)}]]
{result_msg.body}
[[/POLI:MSG]]

Please review this result:
1. Is the task making good progress?
2. Are there issues to address?
3. What should be the next step?

Emit one of these blocks:
- type="continue" with next instructions if task needs more work
- type="revision" if EXECUTER needs to fix something
- type="complete" if the entire task is done successfully

Remember: The original user request was: {user_prompt}"""

        print(f"📤 Sending result back to PLANNER for review...")
        send_keys(PLANNER_PANE, review_prompt)

    # Final status
    print(f"\n{'='*60}")
    if task_complete:
        print(f"✅ Task completed successfully after {round_count} rounds!")
    elif round_count >= max_rounds:
        print(f"⚠️ Reached maximum rounds ({max_rounds})")
    else:
        print(f"❌ Task terminated unexpectedly")
    print(f"{'='*60}\n")

    return task_complete


def interactive_mode():
    """Run orchestrator in interactive mode with continuous dialogue"""
    print("\n" + "="*60)
    print("PoliTerm Orchestrator V2 - Continuous Dialogue Mode")
    print("="*60)
    print("\nThe PLANNER will supervise EXECUTER until task completion")
    print("Type 'exit' or 'quit' to stop")
    print("Type 'status' to check tmux session")
    print("="*60 + "\n")

    while True:
        try:
            user_input = input("\n💭 Enter task for continuous execution: ").strip()

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

            # Get max rounds from user
            max_rounds_input = input("Max rounds (default 10): ").strip()
            max_rounds = int(max_rounds_input) if max_rounds_input.isdigit() else 10

            success = route_continuous(user_input, max_rounds=max_rounds)

            if success:
                print("✨ Task completed successfully through continuous dialogue!")
            else:
                print("⚠️ Task ended without completion")

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            logger.error(f"Error in interactive mode: {e}", exc_info=True)
            print(f"❌ Error: {e}")


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="PoliTerm Orchestrator V2 - Continuous Dialogue")
    parser.add_argument(
        "--task", "-t",
        help="Single task to execute with continuous dialogue"
    )
    parser.add_argument(
        "--task-id",
        help="Specific task ID to use"
    )
    parser.add_argument(
        "--max-rounds", "-r",
        type=int,
        default=10,
        help="Maximum dialogue rounds (default: 10)"
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
        # Single task mode with continuous dialogue
        success = route_continuous(args.task, args.task_id, args.max_rounds)
        sys.exit(0 if success else 1)
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()