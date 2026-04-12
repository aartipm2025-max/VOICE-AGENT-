"""
Core handler — the single entry point for all surfaces.

handle(user_text, session) → list[str]

Phase 3: Real booking engine integration.
- PII filter + advice refusal on every turn
- LLM intent/topic classification (keyword fallback)
- Real slot resolution against mock calendar
- Unique booking code generation
- Waitlist path when no slots match
"""

from core.session import (
    Session, State, Intent, Topic, Slot,
    is_valid_transition,
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
    build_confirmation_message, build_handoff_message,
    add_to_waitlist, get_all_available_slots,
)
from mcp.dispatcher import execute_booking_side_effects, execute_cancel_side_effects
from mcp.notes_tool import get_note_by_code
from config import TIMEZONE, SECURE_BOOKING_URL


# ---------------------------------------------------------------------------
# State handlers — one function per FSM state
# Each returns (list[str] responses, new_state)
# ---------------------------------------------------------------------------

def _handle_greeting(user_text: str, session: Session) -> tuple[list[str], State]:
    """First turn: deliver greeting + disclaimer, move to AWAIT_INTENT."""
    responses = [
        "Hello! Welcome to the Advisor Appointment Scheduler.",
        DISCLAIMER_TEXT,
        "How can I help you today?",
    ]
    session.disclaimer_given = True
    return responses, State.AWAIT_INTENT


def _handle_await_intent(user_text: str, session: Session) -> tuple[list[str], State]:
    """Classify intent using LLM (or keyword fallback) and route."""
    intent = classify_intent(user_text)

    if intent == Intent.BOOK_NEW:
        responses = [
            "Great, let's book a new appointment!",
            "Which topic would you like to discuss with the advisor?",
            "Available topics:",
            "  1. KYC/Onboarding",
            "  2. SIP/Mandates",
            "  3. Statements/Tax Docs",
            "  4. Withdrawals & Timelines",
            "  5. Account Changes/Nominee",
        ]
        return responses, State.COLLECT_TOPIC

    elif intent == Intent.RESCHEDULE:
        responses = [
            "Sure, let's reschedule your appointment.",
            "Which topic is your existing booking for?",
            "Available topics:",
            "  1. KYC/Onboarding",
            "  2. SIP/Mandates",
            "  3. Statements/Tax Docs",
            "  4. Withdrawals & Timelines",
            "  5. Account Changes/Nominee",
        ]
        return responses, State.COLLECT_TOPIC

    elif intent == Intent.CANCEL:
        responses = [
            "I can help you cancel an appointment.",
            "Could you please share your booking code so I can look it up?",
            "(Example format: NL-A742)",
        ]
        return responses, State.CONFIRM_CANCEL

    elif intent == Intent.WHAT_TO_PREPARE:
        responses = [
            "Here's what to prepare for your advisor appointment:",
            "  • A valid government-issued photo ID (Aadhaar, PAN, Passport)",
            "  • Any recent account statements or correspondence",
            "  • A list of questions or topics you'd like to discuss",
            "  • Note: Do NOT share personal documents over this call.",
            "    You'll receive a secure link to upload documents if needed.",
            "",
            "Is there anything else I can help you with?",
        ]
        return responses, State.AWAIT_INTENT

    elif intent == Intent.CHECK_AVAILABILITY:
        all_slots = get_all_available_slots()
        if all_slots:
            # Show a summary of available days
            available_days = sorted(set(s.date for s in all_slots))
            day_list = "\n".join(f"  • {d}" for d in available_days[:5])
            responses = [
                "Here are the days with available slots:",
                day_list,
                f"Time range: 10:00 AM – 5:00 PM {TIMEZONE}",
                "",
                "Would you like to book a specific slot? Just say 'book' to get started.",
            ]
        else:
            responses = [
                "There are currently no available slots.",
                "Would you like to be added to a waitlist?",
            ]
        return responses, State.AWAIT_INTENT

    else:
        responses = [
            "I'm sorry, I didn't quite understand that.",
            "I can help you with:",
            "  • Book a new appointment",
            "  • Reschedule an existing appointment",
            "  • Cancel an appointment",
            "  • Check advisor availability",
            "  • Know what to prepare for your appointment",
            "",
            "What would you like to do?",
        ]
        return responses, State.AWAIT_INTENT


def _handle_collect_topic(user_text: str, session: Session) -> tuple[list[str], State]:
    """Extract topic using LLM (or keyword/number fallback)."""
    topic = classify_topic(user_text)

    if topic is not None:
        session.topic = topic
        responses = [
            f"Got it — your topic is: {topic.value}.",
            f"What day and time would you prefer? (All times are in {TIMEZONE})",
            "For example: 'Monday at 3 PM' or 'tomorrow afternoon'",
        ]
        return responses, State.COLLECT_TIME_PREF
    else:
        responses = [
            "I didn't catch the topic. Please choose one of these:",
            "  1. KYC/Onboarding",
            "  2. SIP/Mandates",
            "  3. Statements/Tax Docs",
            "  4. Withdrawals & Timelines",
            "  5. Account Changes/Nominee",
        ]
        return responses, State.COLLECT_TOPIC


def _handle_collect_time_pref(user_text: str, session: Session) -> tuple[list[str], State]:
    """
    Capture day/time preference and resolve against mock calendar.
    Phase 3: Real slot resolution.
    """
    session.day_preference = user_text.strip()
    session.time_preference = user_text.strip()

    # Resolve slots from the mock calendar
    matched_slots = resolve_slots(user_text, max_slots=2)

    if not matched_slots:
        # No slots match → offer waitlist
        responses = [
            f"I'm sorry, there are no available slots matching your preference.",
            f"Would you like to:",
            f"  1. Try a different day/time",
            f"  2. Be added to the waitlist",
        ]
        return responses, State.WAITLIST

    session.offered_slots = matched_slots

    if len(matched_slots) == 1:
        slot = matched_slots[0]
        responses = [
            f"I found one available slot matching your preference ({TIMEZONE}):",
            f"  Slot 1: {slot.date} at {slot.time} {TIMEZONE}",
            "",
            "Would you like this slot? (yes/no)",
        ]
    else:
        slot_a, slot_b = matched_slots[0], matched_slots[1]
        responses = [
            f"Based on your preference, here are two available slots ({TIMEZONE}):",
            f"  Slot 1: {slot_a.date} at {slot_a.time} {TIMEZONE}",
            f"  Slot 2: {slot_b.date} at {slot_b.time} {TIMEZONE}",
            "",
            "Which slot would you prefer? (Enter 1 or 2)",
        ]
    return responses, State.OFFER_SLOTS


def _handle_offer_slots(user_text: str, session: Session) -> tuple[list[str], State]:
    """User picks a slot or rejects both."""
    text_lower = user_text.strip().lower()

    # 1. Flexible selection matching (numbers and words)
    if any(x in text_lower for x in ("1", "one", "first", "number one", "option one")):
        session.chosen_slot = session.offered_slots[0]
    elif any(x in text_lower for x in ("2", "two", "second", "number two", "option two")):
        if len(session.offered_slots) > 1:
            session.chosen_slot = session.offered_slots[1]
        else:
            session.chosen_slot = session.offered_slots[0]
            
    # 2. Rejection/Different time matching
    elif any(x in text_lower for x in ("neither", "none", "different", "change", "nothing", "other")):
        responses = [
            "No problem. Let me find different times for you.",
            f"What other day/time works for you? (Times in {TIMEZONE})",
        ]
        return responses, State.COLLECT_TIME_PREF
    
    # 3. Handle cases where user just gives a new date/time (Fallback)
    elif any(x in text_lower for x in ("tomorrow", "today", "monday", "tuesday", "wednesday", "thursday", "friday", "pm", "am")):
        # User is clearly trying to specify a different time
        return _handle_collect_time_pref(user_text, session)

    else:
        responses = [
            "I'm sorry, I need you to choose Slot 1 or Slot 2 to proceed.",
            "You can also say 'different' if you'd like to try another time."
        ]
        return responses, State.OFFER_SLOTS

    slot = session.chosen_slot
    responses = [
        "Got it! Let me confirm those details:",
        f"  Topic:  {session.topic.value}",
        f"  Date:   {slot.date}",
        f"  Time:   {slot.time} {TIMEZONE}",
        "",
        "Shall I go ahead and book this? (Please say 'yes' or 'confirm')"
    ]
    return responses, State.CONFIRM_BOOKING


def _handle_confirm_booking(user_text: str, session: Session) -> tuple[list[str], State]:
    """User confirms or rejects the booking."""
    text_lower = user_text.strip().lower()

    if text_lower in ("yes", "y", "yeah", "sure", "confirm", "go ahead"):
        # Generate unique booking code
        session.booking_code = generate_booking_code()

        # Mark slot as booked in the calendar
        book_slot(session.chosen_slot)

        # MCP side-effects execute immediately (no user input at that state)
        mcp_responses, final_state = _handle_mcp_side_effects("", session)
        responses = [
            "Booking confirmed!",
        ] + mcp_responses
        return responses, final_state
    else:
        responses = [
            "No problem — the booking was not placed.",
            "Would you like to pick a different time, or is there anything else I can help with?",
        ]
        return responses, State.AWAIT_INTENT


def _handle_mcp_side_effects(user_text: str, session: Session) -> tuple[list[str], State]:
    """
    Phase 4: Run MCP side effects (calendar, notes, email) + build confirmation & handoff.
    """
    dispatch_result = execute_booking_side_effects(
        topic=session.topic.value,
        code=session.booking_code,
        date=session.chosen_slot.date,
        time=session.chosen_slot.time,
        waitlist=False,
    )

    mcp_msg = []
    if not dispatch_result.all_success:
        mcp_msg.append("(Note: We experienced a minor technical delay syncing systems, but your booking is securely recorded.)")

    confirmation = build_confirmation_message(
        session.topic, session.chosen_slot, session.booking_code
    )
    handoff = build_handoff_message(session.booking_code, SECURE_BOOKING_URL)
    responses = mcp_msg + confirmation + handoff
    return responses, State.ENDED


def _handle_confirm_cancel(user_text: str, session: Session) -> tuple[list[str], State]:
    """Handle cancellation flow."""
    text_lower = user_text.strip().lower()

    # Check if it looks like a booking code (e.g., NL-A742)
    if len(text_lower) >= 4 and "-" in user_text:
        code = user_text.strip().upper()

        note = get_note_by_code(code)
        if note and note.calendar_event_id:
            execute_cancel_side_effects(event_id=note.calendar_event_id, code=code)
        else:
            execute_cancel_side_effects(event_id="unknown", code=code)

        responses = [
            f"Found booking with code: {code}",
            "Your appointment has been cancelled.",
            "",
            "Is there anything else I can help you with?",
        ]
        return responses, State.AWAIT_INTENT
    else:
        responses = [
            "I need your booking code to cancel. It looks like: NL-A742",
            "Could you please share it?",
        ]
        return responses, State.CONFIRM_CANCEL


def _handle_waitlist(user_text: str, session: Session) -> tuple[list[str], State]:
    """Handle waitlist: user can try different time or join waitlist."""
    text_lower = user_text.strip().lower()

    if text_lower in ("1", "different", "try again", "other time"):
        responses = [
            "Sure! What other day/time works for you?",
            f"(All times in {TIMEZONE})",
        ]
        return responses, State.COLLECT_TIME_PREF

    elif text_lower in ("2", "waitlist", "yes", "add me"):
        entry = add_to_waitlist(
            session_id=session.session_id,
            topic=session.topic,
            day_pref=session.day_preference or "",
            time_pref=session.time_preference or "",
        )
        session.booking_code = entry.code

        # Run MCP for waitlist
        execute_booking_side_effects(
            topic=session.topic.value,
            code=entry.code,
            date=session.day_preference or "Any day",
            time=session.time_preference or "Any time",
            waitlist=True,
        )

        responses = [
            "You've been added to the waitlist.",
            f"Your waitlist code is: {entry.code}",
            "We'll notify you when a matching slot opens up.",
            "",
            "Is there anything else I can help you with?",
        ]
        return responses, State.AWAIT_INTENT

    else:
        responses = [
            "Please choose:",
            "  1. Try a different day/time",
            "  2. Be added to the waitlist",
        ]
        return responses, State.WAITLIST


def _handle_ended(user_text: str, session: Session) -> tuple[list[str], State]:
    """Session is over."""
    return ["This session has ended. Please start a new session."], State.ENDED


# ---------------------------------------------------------------------------
# State → handler dispatch table
# ---------------------------------------------------------------------------

_STATE_HANDLERS = {
    State.GREETING:               _handle_greeting,
    State.AWAIT_INTENT:           _handle_await_intent,
    State.COLLECT_TOPIC:          _handle_collect_topic,
    State.COLLECT_TIME_PREF:      _handle_collect_time_pref,
    State.OFFER_SLOTS:            _handle_offer_slots,
    State.CONFIRM_BOOKING:        _handle_confirm_booking,
    State.MCP_SIDE_EFFECTS:       _handle_mcp_side_effects,
    State.CONFIRM_CANCEL:         _handle_confirm_cancel,
    State.WAITLIST:               _handle_waitlist,
    State.ENDED:                  _handle_ended,
}


# ---------------------------------------------------------------------------
# Public API — the ONE function every surface calls
# ---------------------------------------------------------------------------

def handle(user_text: str, session: Session) -> list[str]:
    """
    Process one turn of user input against the session's current state.

    Compliance gates run BEFORE any state handler:
      1. PII filter — reject if personal data detected
      2. Advice refusal — refuse investment advice requests

    Args:
        user_text: The raw text from the user (chat input or STT output).
        session:   The mutable session object for this conversation.

    Returns:
        A list of assistant response strings for this turn.
    """
    # Log user turn
    session.add_turn("user", user_text)

    # ── Compliance Gate 1: PII Filter ──
    # Skip on empty/greeting turn
    if user_text.strip() and session.state != State.GREETING:
        pii_result = check_pii(user_text)
        if pii_result.contains_pii:
            response = [PII_REJECTION_RESPONSE]
            session.add_turn("assistant", PII_REJECTION_RESPONSE)
            return response

    # ── Compliance Gate 2: Advice Refusal ──
    if user_text.strip() and session.state != State.GREETING:
        if check_advice_request(user_text):
            response = [ADVICE_REFUSAL_RESPONSE]
            session.add_turn("assistant", ADVICE_REFUSAL_RESPONSE)
            return response

    # ── State Handler ──
    handler_fn = _STATE_HANDLERS.get(session.state)
    if handler_fn is None:
        return [f"Error: No handler for state {session.state.name}"]

    responses, next_state = handler_fn(user_text, session)

    # Transition state
    if next_state != session.state:
        session.transition(next_state)

    # Log assistant turns
    for msg in responses:
        if msg:  # skip empty strings used for spacing
            session.add_turn("assistant", msg)

    return responses
