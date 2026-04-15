"""
End-to-end verification of the slot selection fix.
Tests multiple scenarios: select slot 1, select slot 2, reject slots.
"""
import os
os.environ["MOCK_GOOGLE_APIS"] = "1"

from core.session import create_session, clear_all_sessions, State
from core.handler import handle
import core.intents
import core.topics

# Force keyword fallback (no LLM needed for testing)
core.intents._llm_available = False
core.topics._llm_available = False

PASS = "✅"
FAIL = "❌"

def run_booking_flow(slot_selection_text, expected_state, test_name):
    """Run a full booking flow with a given slot selection response."""
    clear_all_sessions()
    session = create_session()
    
    # Greeting
    handle("", session)
    
    # Book intent
    handle("I want to book an appointment", session)
    
    # Topic
    handle("KYC", session)
    
    # Time preference
    handle("Tomorrow at 3pm", session)
    
    if session.state != State.SLOT_OFFERED:
        print(f"{FAIL} [{test_name}] Expected SLOT_OFFERED after time, got {session.state.name}")
        return False
    
    # Slot selection (THE KEY STEP)
    resp = handle(slot_selection_text, session)
    
    result = session.state == expected_state
    icon = PASS if result else FAIL
    print(f"{icon} [{test_name}]")
    print(f"   User said: \"{slot_selection_text}\"")
    print(f"   State: {session.state.name} (expected {expected_state.name})")
    print(f"   Bot: {resp[0]}")
    if session.booking_code:
        print(f"   Booking Code: {session.booking_code}")
    print()
    return result

print("=" * 60)
print("  SLOT SELECTION FIX VERIFICATION")
print("=" * 60)
print()

results = []

# Test 1: "Yes" should book (was previously stuck in loop!)
results.append(run_booking_flow("Yes", State.BOOKED, "Affirm with 'Yes'"))

# Test 2: "Book the first one"
results.append(run_booking_flow("Book the first one", State.BOOKED, "Select first slot"))

# Test 3: "I'll take slot 1"
results.append(run_booking_flow("I'll take slot 1", State.BOOKED, "Select slot 1"))

# Test 4: "The second one please"
results.append(run_booking_flow("The second one please", State.BOOKED, "Select second slot"))

# Test 5: "ok sure"
results.append(run_booking_flow("ok sure", State.BOOKED, "Casual confirm"))

# Test 6: "No, different time" should go back
results.append(run_booking_flow("No, I want a different time", State.TOPIC_CONFIRMED, "Reject slots"))

print("=" * 60)
passed = sum(results)
total = len(results)
print(f"  Results: {passed}/{total} passed")
if passed == total:
    print(f"  {PASS} ALL TESTS PASSED — Loop bug is FIXED!")
else:
    print(f"  {FAIL} Some tests failed.")
print("=" * 60)
