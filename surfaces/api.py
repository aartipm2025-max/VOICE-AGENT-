"""
FastAPI REST Interface for the Advisor Appointment Scheduler.

Phase 5: Wrapping the core agnostic handler in a standard HTTP interface.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List

from core.session import get_session, create_session as create_session_core, delete_session, State
from core.handler import handle

app = FastAPI(
    title="Advisor Voice Agent Core API",
    description="REST API wrapping the transport-agnostic voice agent core.",
)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SessionCreateResponse(BaseModel):
    session_id: str
    message: str

class MessageRequest(BaseModel):
    session_id: str
    text: str

class MessageResponse(BaseModel):
    session_id: str
    responses: List[str]
    state: str
    completed: bool

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/session", response_model=SessionCreateResponse)
def create_session():
    """Create a new conversational session and return its ID."""
    session = create_session_core()
    # Execute the empty initial turn to trigger the greeting
    handle("", session)
    return SessionCreateResponse(
        session_id=session.session_id,
        message="Session created successfully"
    )

@app.post("/message", response_model=MessageResponse)
def send_message(req: MessageRequest):
    """
    Send a user message to an active session.
    The core `handle()` function processes state transitions, compliance gates,
    and side-effects automatically.
    """
    session = get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if session.state == State.ENDED:
        return MessageResponse(
            session_id=session.session_id,
            responses=["This session has ended. Please start a new session."],
            state=session.state.name,
            completed=True
        )

    # Core transport-agnostic logic
    responses = handle(req.text, session)
    
    return MessageResponse(
        session_id=session.session_id,
        responses=responses,
        state=session.state.name,
        completed=(session.state == State.ENDED)
    )

@app.get("/session/{session_id}")
def read_session_status(session_id: str):
    """Retrieve the raw session context for debugging or UI purposes."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    return {
        "session_id": session.session_id,
        "state": session.state.name,
        "topic": session.topic.value if session.topic else None,
        "chosen_slot": session.chosen_slot.__dict__ if session.chosen_slot else None,
        "booking_code": session.booking_code,
        "disclaimer_given": session.disclaimer_given,
    }

@app.delete("/session/{session_id}")
def end_session_early(session_id: str):
    """Manually clear a session before it naturally ends/expires."""
    if delete_session(session_id):
        return {"status": "success", "message": f"Session {session_id} deleted"}
    raise HTTPException(status_code=404, detail="Session not found")
