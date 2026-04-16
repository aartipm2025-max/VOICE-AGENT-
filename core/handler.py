"""
Core handler — Refactored for Strict Voice Agent Role.
Rules:
- State > Intent
- Smart Extraction on every turn
- Anti-repeat with auto-selection
- Flexible confirmation
"""

import os
import re
from typing import Optional
from core.session import (
    Session, State, Intent, Topic, Slot,
)
from core.compliance import (
    check_pii, PII_REJECTION_RESPONSE,
    check_advice_request, ADVICE_REFUSAL_RESPONSE,
    DISCLAIMER_TEXT,
)
from core.intents import classify_intent
from core.topics import classify_topic
from core.booking import (
    resolve_slots, generate_booking_code, book_slot,
)
from mcp.dispatcher import execute_booking_side_effects, execute_cancel_side_effects
from config import SECURE_BOOKING_URL

# ---------------------------------------------------------------------------
# Smart Extraction Layer
# ---------------------------------------------------------------------------

def _extract_entities(user_text: str, session: Session):
    """Update global memory from ANY user message."""
    # 1. Topic Extraction
    detected_topic = classify_topic(user_text)
    if detected_topic:
        session.topic = detected_topic
        if session.state == State.START:
            session.transition(State.TOPIC_CONFIRMED)

    # 2. Date Extraction
    text_lower = user_text.lower()

    # Accept common shorthand variants users type in chat.
    tomorrow_aliases = ("tomorrow", "tmrw", "tmr", "tmrw.", "tom")
    if any(alias in text_lower for alias in tomorrow_aliases):
        session.date = "tomorrow"
    elif "today" in text_lower:
        session.date = "today"
    
    # Also capture calendar-style dates like "20 april" / "20 apr 2026".
    date_match = re.search(
        r"\b(\d{1,2})\s+"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)"
        r"(?:\s+(\d{4}))?\b",
        text_lower,
    )
    if date_match:
        day = int(date_match.group(1))
        month = date_match.group(2)
        year = date_match.group(3)
        session.date = f"{day} {month}" + (f" {year}" if year else "")

    # 3. Time Extraction
    time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text_lower)
    if time_match:
        session.time = time_match.group(0)

# ---------------------------------------------------------------------------
# Anti-Repeat Logic
# ---------------------------------------------------------------------------

def _is_repetition(user_text: str, session: Session) -> bool:
    """Check if user is repeating their previous sentence or core details."""
    text_clean = user_text.strip().lower()
    for turn in session.turn_history:
        if turn.role == "user" and turn.text.strip().lower() == text_clean:
            return True
            
    # Check if they are repeating topic/time which was already captured
    if session.topic and session.topic.value.lower() in text_clean:
        if session.state in [State.SLOT_OFFERED, State.CONFIRMATION_PENDING]:
            return True
            
    return False


def _is_availability_query(user_text: str) -> bool:
    """Detect explicit availability-checking language in any state."""
    text_lower = user_text.lower()
    availability_phrases = (
        "what slots are available",
        "which slots are available",
        "any available time",
        "show slots",
        "show me slots",
        "available slots",
        "what times are available",
        "availability",
        "free slots",
        "open slots",
    )
    return any(phrase in text_lower for phrase in availability_phrases)


def _format_date_short(date_text: str) -> str:
    """Convert full slot date text to a compact user-facing format."""
    if not date_text:
        return "that date"
    try:
        from datetime import datetime
        dt = datetime.strptime(date_text, "%A, %d %B %Y")
        return dt.strftime("%d %b").lstrip("0")
    except ValueError:
        return date_text


def _show_available_slots_for_current_context(session: Session, lead_text: Optional[str] = None) -> list[str]:
    """
    Reuse selected topic/date and list available times.
    Never asks for topic/date again when already known.
    """
    if not session.topic or not session.date:
        session.transition(State.TOPIC_CONFIRMED)
        return _respond("Please share topic and date so I can show available slots.", session)

    pref = f"{session.date} any time"
    slots = resolve_slots(pref, max_slots=6)
    if not slots:
        session.transition(State.TOPIC_CONFIRMED)
        session.offered_slots = []
        session.chosen_slot = None
        return _respond(
            f"I could not find available slots for {session.topic.value} on {session.date}. "
            "Please share another date.",
            session,
        )

    session.offered_slots = slots
    session.chosen_slot = None
    session.transition(State.AVAILABILITY_VIEW)
    date_label = _format_date_short(slots[0].date)
    times = ", ".join(slot.time for slot in slots)
    messages = []
    if lead_text:
        messages.append(lead_text)
    messages.append(f"Here are available slots on {date_label}: {times}.")
    messages.append("Tell me which time you want me to book.")
    return _respond(messages, session)

# ---------------------------------------------------------------------------
# Main Handle Logic
# ---------------------------------------------------------------------------

def handle(user_text: str, session: Session) -> list[str]:
    """Single entry point with State Dominance Rule."""
    session.add_turn("user", user_text)
    
    # 1. Smart Entity Extraction (Always run)
    _extract_entities(user_text, session)
    
    # 2. ── Compliance Gates ──
    if user_text.strip() and session.state == State.START:
        pii_result = check_pii(user_text)
        if pii_result.contains_pii:
            return _respond(PII_REJECTION_RESPONSE, session)
        if check_advice_request(user_text):
            return _respond(ADVICE_REFUSAL_RESPONSE, session)

    # 3. ── State Dominance Dispatch ──
    if session.state == State.START:
        return _handle_start(user_text, session)
    
    elif session.state == State.TOPIC_CONFIRMED:
        return _handle_topic_confirmed(user_text, session)
        
    elif session.state == State.TIME_CAPTURED or session.state == State.SLOT_OFFERED:
        return _handle_slot_offering(user_text, session)

    elif session.state == State.BOOKING_FAILED or session.state == State.AVAILABILITY_VIEW:
        return _handle_booking_recovery(user_text, session)
        
    elif session.state == State.CONFIRMATION_PENDING:
        return _handle_confirmation(user_text, session)
        
    elif session.state == State.BOOKED:
        return ["This session is complete. Please start a new one to book again."]
    
    return ["I'm sorry, I'm having trouble tracking the state. Let's try again."]

# ---------------------------------------------------------------------------
# State Handlers
# ---------------------------------------------------------------------------

def _handle_start(user_text: str, session: Session):
    """START State: Only state where intent detection runs."""
    if not user_text.strip():
        resp = ["Hello! Welcome to the Advisor Appointment Scheduler.", DISCLAIMER_TEXT, "How can I help you today?"]
        return _respond(resp, session)

    intent = classify_intent(user_text)
    session.intent = intent

    if intent == Intent.BOOK_NEW:
        if session.topic:
            return _handle_topic_confirmed(user_text, session)
        else:
            resp = [
                "Great, let's book a new appointment!",
                "Which topic would you like to discuss? 1. KYC 2. SIP 3. Tax Docs 4. Withdrawals 5. Account Changes"
            ]
            return _respond(resp, session)
    elif intent == Intent.CANCEL:
        session.transition(State.CANCEL_FLOW)
        return _respond("I can help you cancel. Please share your booking code.", session)
    else:
        return _respond("I can help you book or cancel appointments. What would you like to do?", session)

def _handle_topic_confirmed(user_text: str, session: Session):
    """TOPIC_CONFIRMED: Need Date/Time."""
    if session.date and session.time:
        session.transition(State.TIME_CAPTURED)
        return _handle_slot_offering(user_text, session)

    if session.date and not session.time:
        resp = [f"Got it — your topic is {session.topic.value}.", "I noted the date. What time would you prefer? (IST)"]
        return _respond(resp, session)

    if session.time and not session.date:
        resp = [
            f"Got it — your topic is {session.topic.value}.",
            "Please tell me date so that I can tell you available time slot.",
        ]
        return _respond(resp, session)

    resp = [
        f"Got it — your topic is {session.topic.value}.",
        "Please tell me date so that I can tell you available time slot.",
    ]
    return _respond(resp, session)

def _handle_slot_offering(user_text: str, session: Session):
    """SLOT_OFFERED: Handles both initial slot resolution and user's slot selection."""
    if _is_availability_query(user_text):
        return _show_available_slots_for_current_context(session)
    
    # ── If slots are already offered, interpret user response as selection ──
    if session.state == State.SLOT_OFFERED and session.offered_slots:
        text_lower = user_text.lower()
        
        # Detect rejection / different time request
        if any(x in text_lower for x in ["no", "neither", "different", "other time", "none"]):
            session.transition(State.TOPIC_CONFIRMED)
            session.date = None
            session.time = None
            return _respond("No problem. What other day and time would you prefer? (IST)", session)
        
        # Detect slot 2 selection
        if any(x in text_lower for x in ["second", "2", "two", "later", "other"]) and len(session.offered_slots) > 1:
            session.chosen_slot = session.offered_slots[1]
            session.transition(State.CONFIRMATION_PENDING)
            return _handle_confirmation("yes", session)
        
        # Default: select slot 1 for any affirmative / selection response
        # ("yes", "first", "1", "book", "confirm", "ok", "sure", topic repetition, etc.)
        session.chosen_slot = session.offered_slots[0]
        session.transition(State.CONFIRMATION_PENDING)
        return _handle_confirmation("yes", session)

    # ── Initial slot resolution (from TIME_CAPTURED state) ──
    pref = f"{session.date or ''} {session.time or user_text}"
    slots = resolve_slots(pref)
    
    if not slots:
        session.transition(State.BOOKING_FAILED)
        fallback_pref = f"{session.date or ''} any time"
        fallback_slots = resolve_slots(fallback_pref, max_slots=6)
        if fallback_slots:
            session.offered_slots = fallback_slots
            lead = f"{session.time or 'That time'} is unavailable."
            return _show_available_slots_for_current_context(
                session,
                lead_text=lead,
            )
        return _respond("I'm sorry, no slots match for that date. Try another day?", session)
        
    session.offered_slots = slots
    session.transition(State.SLOT_OFFERED)
    
    slot_lines = [f"Slot {i+1}: {s.date} at {s.time}" for i, s in enumerate(slots)]
    resp = [f"I found {len(slots)} slot(s) for you:"] + slot_lines + ["Which one should I book?"]
    return _respond(resp, session)

def _handle_confirmation(user_text: str, session: Session):
    """CONFIRMATION_PENDING: Flexible logic."""
    text_lower = user_text.lower()

    # Availability intent should not be interpreted as booking confirmation.
    if _is_availability_query(user_text):
        session.transition(State.AVAILABILITY_VIEW)
        return _show_available_slots_for_current_context(session)
    
    # Handle auto-selection from previous state
    if user_text == "yes" and not session.chosen_slot:
         session.chosen_slot = session.offered_slots[0]

    # Explicit Cancel
    if any(x in text_lower for x in ["no", "cancel", "stop"]):
        session.transition(State.START)
        return _respond("No problem. Booking cancelled. Anything else?", session)

    # Confirmation by rep or intent
    is_confirm = any(x in text_lower for x in ["yes", "confirm", "ok", "book", "correct"]) or _is_repetition(user_text, session)
    
    if is_confirm:
        if not session.chosen_slot:
            return _respond("I couldn't identify the slot to confirm. Please select one from the offered options.", session)

        # Prevent duplicate booking if another session has already taken this slot.
        booked_now = book_slot(session.chosen_slot)
        if not booked_now:
            pref = f"{session.date or ''} {session.time or ''}".strip()
            alternatives = resolve_slots(pref or "next available")
            if not alternatives:
                session.transition(State.TOPIC_CONFIRMED)
                session.offered_slots = []
                session.chosen_slot = None
                return _respond(
                    "That slot was just booked by someone else, and I could not find nearby alternatives. "
                    "Please share another preferred day and time (IST).",
                    session,
                )

            session.offered_slots = alternatives
            session.chosen_slot = None
            session.transition(State.SLOT_OFFERED)
            alt_lines = [f"Slot {i+1}: {s.date} at {s.time}" for i, s in enumerate(alternatives)]
            return _respond(
                ["That slot was just taken. Here are the next available options:"] + alt_lines + ["Which one should I book?"],
                session,
            )

        # EXECUTE BOOKING
        code = f"NL-{generate_booking_code().split('-')[1]}"
        session.booking_code = code
        
        execute_booking_side_effects(
            topic=session.topic.value,
            code=code,
            date=session.chosen_slot.date,
            time=session.chosen_slot.time
        )
        
        final_resp = [
            "Your booking is confirmed.",
            f"Topic: {session.topic.value}",
            f"Date: {session.chosen_slot.date}",
            f"Time: {session.chosen_slot.time} IST",
            f"Booking Code: {code}",
            f"Complete your details securely here: https://secure.app/{code}"
        ]
        session.transition(State.BOOKED)
        return _respond(final_resp, session)

    # Otherwise, ask again nicely
    session.transition(State.CONFIRMATION_PENDING)
    return _respond(f"Shall I book your {session.topic.value} session for {session.chosen_slot.time}?", session)


def _handle_booking_recovery(user_text: str, session: Session):
    """Handles BOOKING_FAILED/AVAILABILITY_VIEW follow-ups."""
    if _is_availability_query(user_text):
        session.transition(State.AVAILABILITY_VIEW)
        return _show_available_slots_for_current_context(session)

    # Reuse existing slot selection behavior when user picks one of shown options.
    session.transition(State.SLOT_OFFERED)
    return _handle_slot_offering(user_text, session)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _respond(messages, session: Session):
    """Log to memory and return list of strings."""
    if isinstance(messages, str):
        messages = [messages]
    for m in messages:
        session.add_turn("assistant", m)
    return messages
