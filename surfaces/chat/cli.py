"""
CLI Chat Surface — Phase 1 development and test harness.

Run with:  python -m surfaces.chat.cli
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.session import create_session
from core.handler import handle


def main():
    print("=" * 60)
    print("  Advisor Appointment Scheduler — CLI Chat")
    print("  Type 'quit' or 'exit' to end the session.")
    print("=" * 60)
    print()

    session = create_session()
    print(f"[Session: {session.session_id[:8]}...]\n")

    # First turn: greeting is triggered automatically
    responses = handle("", session)
    for line in responses:
        print(f"  Agent: {line}")
    print()

    # Conversation loop
    while session.state.name != "ENDED":
        try:
            user_input = input("  You:   ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n  Agent: Session ended. Goodbye!")
            break

        if user_input.lower() in ("quit", "exit"):
            print("\n  Agent: Session ended. Goodbye!")
            break

        if not user_input:
            continue

        responses = handle(user_input, session)
        for line in responses:
            print(f"  Agent: {line}")
        print()

    print(f"\n[Final state: {session.state.name}]")
    print(f"[Turns logged: {len(session.turn_history)}]")


if __name__ == "__main__":
    main()
