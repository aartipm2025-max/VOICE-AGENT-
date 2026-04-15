import sys
from unittest.mock import MagicMock

# Mock LLM and MCP before importing core modules
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()

import core.intents
import core.topics
import mcp.dispatcher

# Mock the classifiers and tool calls
core.intents.classify_intent = MagicMock(return_value=MagicMock(value="book_new"))
# In core/session.py, Intent is an Enum. Let's import it properly.
from core.session import Intent, Topic, State
core.intents.classify_intent = MagicMock(return_value=Intent.BOOK_NEW)
core.topics.classify_topic = MagicMock(return_value=Topic.KYC_ONBOARDING)
mcp.dispatcher.execute_booking_side_effects = MagicMock(return_value=MagicMock(all_success=True))

from core.session import create_session
from core.handler import handle

def verify_logic():
    print("--- Verifying Core Logic Flow (Mocked LLM/MCP) ---")
    session = create_session()
    
    # 1. Start
    r = handle("", session)
    print(f"Greet: {r[0]}")
    
    # 2. Book
    r = handle("I want to book", session)
    print(f"User: I want to book -> Bot: {r[-1]}")
    print(f"State: {session.state}")
    
    # 3. Topic (Already mocked to KYC)
    r = handle("KYC", session)
    print(f"User: KYC -> Bot: {r[-1]}")
    print(f"State: {session.state}")
    
    # 4. Time
    r = handle("Tomorrow at 10am", session)
    print(f"User: Tomorrow at 10am -> Bot: {r[-1]}")
    print(f"State: {session.state}")
    
    # 5. Confirm
    r = handle("Yes, book it", session)
    print(f"User: Yes -> Bot: {r[0]}")
    print(f"State: {session.state}")

if __name__ == "__main__":
    verify_logic()
