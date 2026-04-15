"""
Session and Finite State Machine for the Advisor Appointment Scheduler.

The FSM controls which state we're in; the LLM (Phase 2) will generate
natural language *within* a state. In Phase 1, responses are hardcoded stubs.
"""

import uuid
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class State(Enum):
    """Refined Voice Agent States."""
    START                = auto()
    TOPIC_CONFIRMED      = auto()
    TIME_CAPTURED        = auto()
    SLOT_OFFERED         = auto()
    CONFIRMATION_PENDING = auto()
    BOOKED               = auto()
    CANCEL_FLOW          = auto()
    ENDED                = auto()

class Intent(Enum):
    """Supported intents."""
    BOOK_NEW           = "book_new"
    RESCHEDULE         = "reschedule"
    CANCEL             = "cancel"
    WHAT_TO_PREPARE    = "what_to_prepare"
    CHECK_AVAILABILITY = "check_availability"
    UNKNOWN            = "unknown"

class Topic(Enum):
    """The 5 strict consultation topics."""
    KYC_ONBOARDING          = "KYC/Onboarding"
    SIP_MANDATES            = "SIP/Mandates"
    STATEMENTS_TAX_DOCS     = "Statements/Tax Docs"
    WITHDRAWALS_TIMELINES   = "Withdrawals & Timelines"
    ACCOUNT_CHANGES_NOMINEE = "Account Changes/Nominee"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Turn:
    """A single conversational turn."""
    role: str   # "user" or "assistant"
    text: str

@dataclass
class Slot:
    """A proposed appointment slot."""
    date: str       # e.g. "Monday, 14 April 2026"
    time: str       # e.g. "3:00 PM"
    advisor_id: str  # e.g. "ADV-01"

@dataclass
class Session:
    """
    Holds all mutable state for a single conversation.
    Global memory in sync with Voice Agent requirements.
    """
    session_id:       str            = field(default_factory=lambda: str(uuid.uuid4()))
    state:            State          = State.START
    
    # Global Memory
    intent:           Optional[Intent] = None
    topic:            Optional[Topic] = None
    date:             Optional[str]   = None
    time:             Optional[str]   = None
    offered_slots:    list            = field(default_factory=list)
    last_offered_slots: list          = field(default_factory=list)
    chosen_slot:      Optional[Slot]  = None
    booking_code:     Optional[str]   = None
    confirmation_email: Optional[str] = None
    email_sent:       bool            = False
    
    disclaimer_given: bool           = False
    turn_history:     list           = field(default_factory=list)

    def add_turn(self, role: str, text: str) -> None:
        """Append a turn to the conversation history."""
        self.turn_history.append(Turn(role=role, text=text))

    def transition(self, new_state: State) -> None:
        """Move the FSM to a new state."""
        self.state = new_state



# ---------------------------------------------------------------------------
# Valid FSM transitions — used for validation
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[State, list[State]] = {
    State.START:                [State.TOPIC_CONFIRMED, State.CANCEL_FLOW],
    State.TOPIC_CONFIRMED:      [State.TIME_CAPTURED, State.SLOT_OFFERED],
    State.TIME_CAPTURED:        [State.SLOT_OFFERED],
    State.SLOT_OFFERED:         [State.CONFIRMATION_PENDING, State.TIME_CAPTURED],
    State.CONFIRMATION_PENDING: [State.BOOKED, State.START],
    State.BOOKED:               [State.ENDED],
    State.CANCEL_FLOW:          [State.ENDED, State.START],
    State.ENDED:                [],
}


def is_valid_transition(from_state: State, to_state: State) -> bool:
    """Check if a state transition is allowed by the FSM."""
    return to_state in VALID_TRANSITIONS.get(from_state, [])


# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

_session_store: dict[str, Session] = {}


def create_session() -> Session:
    """Create a new session and add it to the store."""
    session = Session()
    _session_store[session.session_id] = session
    return session


def get_session(session_id: str) -> Optional[Session]:
    """Retrieve a session by ID."""
    return _session_store.get(session_id)


def delete_session(session_id: str) -> bool:
    """Remove a session from the store. Returns True if it existed."""
    return _session_store.pop(session_id, None) is not None


def get_all_sessions() -> dict[str, Session]:
    """Return all active sessions (for debugging)."""
    return dict(_session_store)


def clear_all_sessions() -> None:
    """Wipe the store (useful for tests)."""
    _session_store.clear()
