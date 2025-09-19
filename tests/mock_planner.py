#!/usr/bin/env python3
"""
Mock PLANNER TUI for testing PoliTerm Orchestrator
Simulates a simple planning AI that responds to commands
"""

import sys
import json
import time
import uuid
import re


def extract_task_id(text):
    """Extract task ID from input"""
    match = re.search(r'TASK_ID=(\S+)', text)
    if match:
        return match.group(1)
    return str(uuid.uuid4())


def create_plan_for_request(request):
    """Generate a simple plan based on the request"""
    # Simple keyword-based planning
    plan_steps = []

    if "hello.txt" in request.lower() or "file" in request.lower():
        plan_steps = [
            "Step 1: Navigate to the appropriate directory",
            "Step 2: Create the file 'hello.txt'",
            "Step 3: Write 'Hello, PoliTerm!' to the file",
            "Step 4: Verify the file was created successfully",
            "Step 5: Report completion status"
        ]
    elif "analyze" in request.lower():
        plan_steps = [
            "Step 1: Locate the target for analysis",
            "Step 2: Examine the structure and content",
            "Step 3: Generate analysis report",
            "Step 4: Summarize findings"
        ]
    elif "test" in request.lower():
        plan_steps = [
            "Step 1: Prepare test environment",
            "Step 2: Execute test cases",
            "Step 3: Collect results",
            "Step 4: Generate test report"
        ]
    else:
        plan_steps = [
            "Step 1: Parse and understand the request",
            "Step 2: Execute the main task",
            "Step 3: Verify results",
            "Step 4: Report completion"
        ]

    return "\n".join(plan_steps)


def main():
    print("Mock PLANNER v1.0 - Ready")
    print("Type 'help' for available commands")
    print()

    buffer = []
    in_multiline = False

    while True:
        try:
            if in_multiline:
                line = input()
            else:
                line = input("planner> ")

            # Check for multiline input start
            if "TASK_ID=" in line:
                in_multiline = True
                buffer = [line]
                continue

            # Accumulate multiline input
            if in_multiline:
                buffer.append(line)

                # Check if we have complete input
                full_input = "\n".join(buffer)

                if "Please" in line and "tagged block" in line:
                    # We have the complete request, process it
                    in_multiline = False

                    # Extract task ID
                    task_id = extract_task_id(full_input)

                    # Extract the actual user request
                    request_match = re.search(r'User request:\s*(.*?)(?:\n\nPlease|\Z)',
                                            full_input, re.DOTALL)
                    if request_match:
                        user_request = request_match.group(1).strip()
                    else:
                        user_request = "Unknown request"

                    print(f"\nAnalyzing request: {user_request[:50]}...")
                    time.sleep(1)  # Simulate thinking

                    # Generate plan
                    plan = create_plan_for_request(user_request)

                    # Emit POLI:MSG block
                    meta = {
                        "to": "EXECUTER",
                        "type": "plan",
                        "id": task_id
                    }

                    print(f"[[POLI:MSG {json.dumps(meta)}]]")
                    print("<PLAN>")
                    print(plan)
                    print("</PLAN>")
                    print("[[/POLI:MSG]]")
                    print()

                    buffer = []
                    continue

            # Handle standalone commands
            if line.strip().lower() == "help":
                print("Mock PLANNER Commands:")
                print("  help     - Show this help")
                print("  status   - Show current status")
                print("  exit     - Exit the mock planner")
                print()

            elif line.strip().lower() == "status":
                print("Status: Ready and waiting for tasks")
                print()

            elif line.strip().lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            elif "EXECUTER" in line and "replied" in line:
                # Handle result from executer
                print("\nProcessing EXECUTER result...")
                time.sleep(0.5)

                # Provide summary
                print("\n=== Summary for User ===")
                print("Task completed successfully!")
                print("The EXECUTER has executed all planned steps.")
                print("All objectives have been achieved.")
                print("======================\n")

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