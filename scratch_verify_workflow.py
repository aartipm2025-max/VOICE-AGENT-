import uuid
from core.session import create_session, get_session, State
from core.handler import handle

def test_workflow():
    print("--- Starting Workflow Verification ---")
    
    # 1. Start Session
    session = create_session()
    print(f"Session Created: {session.session_id}")
    print(f"Initial State: {session.state.name}")
    
    # 2. Get Greeting
    print("\n[Bot Greeting]")
    responses = handle("", session)
    for r in responses:
        print(f"Bot: {r}")
    
    # 3. Request Booking
    print("\n[User]: I'd like to book an appointment")
    responses = handle("I'd like to book an appointment", session)
    for r in responses:
        print(f"Bot: {r}")
    print(f"State: {session.state.name}")
    
    # 4. Provide Topic
    print("\n[User]: KYC/Onboarding")
    responses = handle("KYC/Onboarding", session)
    for r in responses:
        print(f"Bot: {r}")
    print(f"State: {session.state.name}")
    
    # 5. Provide Time Preference
    print("\n[User]: Next Monday at 3 PM")
    responses = handle("Next Monday at 3 PM", session)
    for r in responses:
        print(f"Bot: {r}")
    print(f"State: {session.state.name}")
    
    # 6. Select Slot
    if session.state.name == "OFFER_SLOTS":
        print("\n[User]: I'll take the first one")
        responses = handle("I'll take the first one", session)
        for r in responses:
            print(f"Bot: {r}")
        print(f"State: {session.state.name}")
    else:
        print(f"\n[Error]: Expected state OFFER_SLOTS, but got {session.state.name}")

if __name__ == "__main__":
    test_workflow()
