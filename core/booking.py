"""
Booking Engine — Phase 3

Components:
  1. Mock calendar with in-memory availability (next 7 days)
  2. Slot resolution: match user day/time preference → 2 slots
  3. Booking code generator: "XX-YZZZ" format
  4. Confirmation builder: formatted string with IST timezone
  5. Waitlist path: store waitlist entries when no slots match
"""

import random
import string
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

from core.session import Slot, Topic
from config import TIMEZONE


# ---------------------------------------------------------------------------
# Mock Calendar — in-memory availability
# ---------------------------------------------------------------------------

# Time windows advisors are available (24h format)
_AVAILABLE_HOURS = [
    (10, 0),   # 10:00 AM
    (10, 30),  # 10:30 AM
    (11, 0),   # 11:00 AM
    (11, 30),  # 11:30 AM
    (14, 0),   # 2:00 PM
    (14, 30),  # 2:30 PM
    (15, 0),   # 3:00 PM
    (15, 30),  # 3:30 PM
    (16, 0),   # 4:00 PM
    (16, 30),  # 4:30 PM
]

_ADVISORS = ["ADV-01", "ADV-02", "ADV-03"]

# Booked slots: set of (date_str, time_str) that are taken
_booked_slots: set[tuple[str, str]] = set()

# Waitlist entries
_waitlist: list[dict] = []


def _get_next_7_days() -> list[datetime]:
    """Return datetime objects for the next 7 weekdays (Mon-Fri)."""
    today = datetime.now()
    days = []
    current = today + timedelta(days=1)  # start from tomorrow
    while len(days) < 7:
        if current.weekday() < 5:  # Mon=0 to Fri=4
            days.append(current)
        current += timedelta(days=1)
    return days


def _format_date(dt: datetime) -> str:
    """Format: 'Monday, 14 April 2026'"""
    return dt.strftime("%A, %d %B %Y")


def _format_time(hour: int, minute: int) -> str:
    """Format: '3:00 PM' or '10:30 AM'"""
    dt = datetime.now().replace(hour=hour, minute=minute)
    result = dt.strftime("%I:%M %p").lstrip("0")
    return result


def get_all_available_slots() -> list[Slot]:
    """
    Generate all available slots for the next 7 weekdays.
    Excludes already-booked slots.
    """
    slots = []
    for day in _get_next_7_days():
        for hour, minute in _AVAILABLE_HOURS:
            date_str = _format_date(day)
            time_str = _format_time(hour, minute)
            if (date_str, time_str) not in _booked_slots:
                advisor = random.choice(_ADVISORS)
                slots.append(Slot(date=date_str, time=time_str, advisor_id=advisor))
    return slots


# ---------------------------------------------------------------------------
# Day/Time preference parsing
# ---------------------------------------------------------------------------

_DAY_NAMES = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "tomorrow": None,  # special case
    "today": None,     # special case
}

_TIME_PREFERENCES = {
    "morning":   (10, 12),
    "afternoon": (12, 17),
    "evening":   (16, 18),
    "early":     (10, 12),
    "late":      (15, 17),
}


def _parse_day_preference(text: str) -> list[int] | None:
    """
    Parse user text into weekday number(s).
    Returns list of weekday ints (Mon=0..Fri=4), or None for "any day".
    """
    text_lower = text.lower()

    if "tomorrow" in text_lower:
        tomorrow = datetime.now() + timedelta(days=1)
        if tomorrow.weekday() < 5:
            return [tomorrow.weekday()]
        # If tomorrow is weekend, return Monday
        return [0]

    if "today" in text_lower:
        today = datetime.now()
        if today.weekday() < 5:
            return [today.weekday()]
        return None

    # Look for specific day names
    matched_days = []
    for day_name, day_num in _DAY_NAMES.items():
        if day_name in text_lower and day_num is not None:
            if day_num not in matched_days:
                matched_days.append(day_num)

    return matched_days if matched_days else None


def _parse_time_preference(text: str) -> tuple[int, int] | None:
    """
    Parse user text into a time range (start_hour, end_hour).
    Returns None for "any time".
    """
    text_lower = text.lower()

    # Check named time preferences
    for pref_name, (start, end) in _TIME_PREFERENCES.items():
        if pref_name in text_lower:
            return (start, end)

    # Try to parse specific times like "3 PM", "3:00 PM", "15:00"
    import re

    # Match "3 PM", "3:00 PM", "3:30pm"
    match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text_lower)
    if match:
        hour = int(match.group(1))
        ampm = match.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        # Give a 2-hour window around the requested time
        return (max(10, hour - 1), min(17, hour + 1))

    # Match 24h format "15:00"
    match = re.search(r'(\d{2}):(\d{2})', text_lower)
    if match:
        hour = int(match.group(1))
        if 10 <= hour <= 17:
            return (max(10, hour - 1), min(17, hour + 1))

    return None


# ---------------------------------------------------------------------------
# Slot resolution — the core matching function
# ---------------------------------------------------------------------------

def resolve_slots(
    user_text: str,
    max_slots: int = 2,
) -> list[Slot]:
    """
    Match user's day/time preference against available calendar slots.

    Args:
        user_text: Raw user input with day/time preference.
        max_slots: Maximum number of slots to return (default 2).

    Returns:
        List of matching Slot objects (max 2), or empty if none match.
    """
    all_slots = get_all_available_slots()
    day_pref = _parse_day_preference(user_text)
    time_pref = _parse_time_preference(user_text)

    matched = []

    for slot in all_slots:
        # Parse the slot's day
        try:
            slot_dt = datetime.strptime(slot.date, "%A, %d %B %Y")
        except ValueError:
            continue

        # Filter by day preference
        if day_pref is not None:
            if slot_dt.weekday() not in day_pref:
                continue

        # Filter by time preference
        if time_pref is not None:
            start_h, end_h = time_pref
            # Parse slot time
            try:
                slot_time = datetime.strptime(slot.time.strip(), "%I:%M %p")
                slot_hour = slot_time.hour
            except ValueError:
                continue

            if not (start_h <= slot_hour <= end_h):
                continue

        matched.append(slot)

        if len(matched) >= max_slots:
            break

    return matched


# ---------------------------------------------------------------------------
# Booking code generator
# ---------------------------------------------------------------------------

_generated_codes: set[str] = set()


def generate_booking_code() -> str:
    """
    Generate a unique booking code in format 'XX-YZZZ'.
      XX  = 2 random uppercase letters
      Y   = 1 random uppercase letter
      ZZZ = 3 random digits
    Example: 'NL-A742'

    Optimized for TTS readability:
      Agent reads as 'N-L dash A-7-4-2'
    """
    while True:
        prefix = ''.join(random.choices(string.ascii_uppercase, k=2))
        mid = random.choice(string.ascii_uppercase)
        suffix = ''.join(random.choices(string.digits, k=3))
        code = f"{prefix}-{mid}{suffix}"

        if code not in _generated_codes:
            _generated_codes.add(code)
            return code


# ---------------------------------------------------------------------------
# Confirmation builder
# ---------------------------------------------------------------------------

def build_confirmation_message(topic: Topic, slot: Slot, code: str) -> list[str]:
    """
    Build the structured confirmation message.
    Always includes: topic, full date, time, IST timezone, and booking code.
    """
    return [
        f"Your tentative appointment for {topic.value} is booked for "
        f"{slot.date} at {slot.time} {TIMEZONE}.",
        f"Your booking code is: {code}",
    ]


def build_handoff_message(code: str, secure_url: str) -> list[str]:
    """Build the final handoff message with secure link."""
    return [
        "",
        f"Please visit {secure_url} and enter your booking code "
        f"within 2 hours to provide your contact details and finalize the appointment.",
        "",
        "Thank you for using the Advisor Appointment Scheduler. Goodbye!",
    ]


# ---------------------------------------------------------------------------
# Waitlist management
# ---------------------------------------------------------------------------

@dataclass
class WaitlistEntry:
    """A waitlist entry for when no slots match preferences."""
    session_id: str
    topic: Topic
    day_preference: str
    time_preference: str
    code: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


def add_to_waitlist(
    session_id: str,
    topic: Topic,
    day_pref: str,
    time_pref: str,
) -> WaitlistEntry:
    """Add user to the waitlist when no slots match."""
    code = generate_booking_code()
    entry = WaitlistEntry(
        session_id=session_id,
        topic=topic,
        day_preference=day_pref,
        time_preference=time_pref,
        code=code,
    )
    _waitlist.append({"entry": entry})
    return entry


def get_waitlist() -> list[dict]:
    """Return all waitlist entries (for debugging)."""
    return list(_waitlist)


# ---------------------------------------------------------------------------
# Slot booking (marks a slot as taken)
# ---------------------------------------------------------------------------

def book_slot(slot: Slot) -> None:
    """Mark a slot as booked so it won't appear in future availability."""
    _booked_slots.add((slot.date, slot.time))


# ---------------------------------------------------------------------------
# Reset functions (for testing)
# ---------------------------------------------------------------------------

def reset_calendar() -> None:
    """Clear all bookings and waitlist (for tests)."""
    _booked_slots.clear()
    _waitlist.clear()
    _generated_codes.clear()
