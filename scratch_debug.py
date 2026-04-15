import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.session import Session, State, Topic
from core.handler import handle

session = Session()
print(f"Init: {session.state}")

r1 = handle("", session)
print(f"1. State: {session.state}, Resp: {r1}")

r2 = handle("I want to book for KYC", session)
print(f"2. State: {session.state}, Resp: {r2}")

r3 = handle("tomorrow at 3pm", session)
print(f"3. State: {session.state}, Resp: {r3}")

r4 = handle("no", session)
print(f"4. State: {session.state}, Resp: {r4}\nTurns:")
for t in session.turn_history:
    print(t)
