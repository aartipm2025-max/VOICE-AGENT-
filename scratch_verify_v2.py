import os
import sys
from unittest.mock import MagicMock

# Set mock env var for Google APIs
os.environ["MOCK_GOOGLE_APIS"] = "1"
os.environ["GEMINI_API_KEY"] = "mock_key"

# Mock the LLM before it gets used in core.intents and core.topics
# This is tricky because the lazy init in those modules might still fail on import if the lib isn't there.
# But I just installed them, hopefully.

def run_simulation():
    from core.session import create_session, Intent, Topic, State
    from core.handler import handle
    import core.intents
    import core.topics
    
    # Force keyword fallback by making LLM unavailable
    core.intents._llm_available = False
    core.topics._llm_available = False
    
    print("--- Starting Full Logic Simulation (MOCK_GOOGLE_APIS=1) ---")
    session = create_session()
    
    # Turn 1: Greeting
    print("\n[INIT]")
    resp = handle("", session)
    print(f"Bot: {resp}")
    
    # Turn 2: Booking intent
    print("\n[USER]: I want to book an appointment")
    resp = handle("I want to book an appointment", session)
    print(f"Bot: {resp}")
    print(f"State: {session.state.name}")
    
    # Turn 3: Topic
    print("\n[USER]: KYC Onboarding")
    resp = handle("KYC Onboarding", session)
    print(f"Bot: {resp}")
    print(f"State: {session.state.name}")
    
    # Turn 4: Time
    print("\n[USER]: Tomorrow at 3pm")
    resp = handle("Tomorrow at 3pm", session)
    print(f"Bot: {resp}")
    print(f"State: {session.state.name}")
    
    # Turn 5: Confirm
    if session.state == State.SLOT_OFFERED:
        print("\n[USER]: Yes please")
        resp = handle("Yes please", session)
        print(f"Bot: {resp}")
        print(f"State: {session.state.name}")
    else:
        print(f"\n[ERROR]: Expected SLOT_OFFERED, got {session.state.name}")

if __name__ == "__main__":
    try:
        run_simulation()
    except Exception as e:
        print(f"Simulation failed with error: {e}")
        import traceback
        traceback.print_exc()
