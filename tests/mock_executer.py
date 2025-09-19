#!/usr/bin/env python3
"""
Mock EXECUTER TUI for testing PoliTerm Orchestrator
Simulates an execution AI that performs planned tasks
"""

import sys
import json
import time
import os
import re


def extract_task_id(text):
    """Extract task ID from input"""
    # Try to find in the message metadata
    meta_match = re.search(r'\[\[POLI:MSG\s+(\{.*?\})\]\]', text)
    if meta_match:
        try:
            meta = json.loads(meta_match.group(1))
            return meta.get("id", "unknown")
        except:
            pass

    # Fallback to direct ID search
    id_match = re.search(r'id=(\S+)', text)
    if id_match:
        return id_match.group(1)

    return "unknown"


def extract_plan(text):
    """Extract plan content from POLI message"""
    plan_match = re.search(r'<PLAN>(.*?)</PLAN>', text, re.DOTALL)
    if plan_match:
        return plan_match.group(1).strip()
    return ""


def execute_plan(plan, task_id):
    """Simulate executing a plan"""
    steps = []
    results = []

    # Parse steps from plan
    for line in plan.split('\n'):
        if line.strip().startswith('Step'):
            steps.append(line.strip())

    if not steps:
        steps = ["Execute the requested task"]

    # Simulate execution
    for i, step in enumerate(steps, 1):
        # Emit status update
        status_meta = {
            "to": "PLANNER",
            "type": "status",
            "id": f"{task_id}-status-{i}"
        }

        print(f"\n[[POLI:MSG {json.dumps(status_meta)}]]")
        print("<STATUS>")
        print(f"Executing: {step}")
        print(f"Progress: {i}/{len(steps)} steps completed")
        print("</STATUS>")
        print("[[/POLI:MSG]]")

        time.sleep(0.5)  # Simulate work

        # Generate result for this step
        if "create" in step.lower() and "file" in step.lower():
            # Actually create a simple file for testing
            try:
                with open("hello.txt", "w") as f:
                    f.write("Hello, PoliTerm!\n")
                results.append(f"✓ File created successfully")
            except Exception as e:
                results.append(f"✗ Failed to create file: {e}")
        elif "verify" in step.lower():
            results.append("✓ Verification completed")
        else:
            results.append(f"✓ {step} - Completed")

    return results


def main():
    print("Mock EXECUTER v1.0 - Ready")
    print("Type 'help' for available commands")
    print()

    buffer = []
    in_multiline = False

    while True:
        try:
            if in_multiline:
                line = input()
            else:
                line = input("executer> ")

            # Check for POLI message start
            if "[[POLI:MSG" in line or "You received" in line:
                in_multiline = True
                buffer = [line]
                continue

            # Accumulate multiline input
            if in_multiline:
                buffer.append(line)

                # Check if we have complete input
                if "emit a RESULT block" in line or "with id=" in line:
                    # We have the complete request, process it
                    in_multiline = False
                    full_input = "\n".join(buffer)

                    # Extract task ID and plan
                    task_id = extract_task_id(full_input)
                    plan = extract_plan(full_input)

                    if plan:
                        print(f"\nReceived plan with task ID: {task_id}")
                        print("Starting execution...")

                        # Execute the plan
                        results = execute_plan(plan, task_id)

                        # Emit final result block
                        result_meta = {
                            "to": "PLANNER",
                            "type": "result",
                            "id": task_id
                        }

                        print(f"\n[[POLI:MSG {json.dumps(result_meta)}]]")
                        print("<RESULT>")
                        print("Summary: Task execution completed successfully")
                        print("Details:")
                        for result in results:
                            print(f"  - {result}")
                        print("Issues/Blockers: None")
                        print("Next Steps: Task complete, awaiting next instruction")
                        print("</RESULT>")
                        print("[[/POLI:MSG]]")
                        print()
                    else:
                        print("No plan found in input")

                    buffer = []
                    continue

            # Handle standalone commands
            if line.strip().lower() == "help":
                print("Mock EXECUTER Commands:")
                print("  help     - Show this help")
                print("  status   - Show current status")
                print("  ls       - List current directory")
                print("  exit     - Exit the mock executer")
                print()

            elif line.strip().lower() == "status":
                print("Status: Ready to execute plans")
                print(f"Working directory: {os.getcwd()}")
                print()

            elif line.strip().lower() == "ls":
                files = os.listdir('.')
                print("Files in current directory:")
                for f in files:
                    print(f"  {f}")
                print()

            elif line.strip().lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            elif line.strip() and not in_multiline:
                # Echo back for simple inputs
                print(f"Received: {line}")

        except EOFError:
            break
        except KeyboardInterrupt:
            print("\nInterrupted")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()