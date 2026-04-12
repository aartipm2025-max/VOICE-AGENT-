"""
MCP Dispatcher — Orchestrates all 3 MCP tool calls sequentially.

Order matters:
  1. Calendar hold (creates event_id)
  2. Notes append (references event_id)
  3. Email draft (references both)

Retry logic: Each tool gets 1 retry on failure.
If a tool fails after retry, the dispatcher continues with remaining tools
and reports partial success.
"""

from dataclasses import dataclass, field
from typing import Optional
import logging

from mcp.calendar_tool import (
    create_tentative_hold, cancel_calendar_hold,
    CalendarHoldResult,
)
from mcp.notes_tool import append_booking_note, NoteResult
from mcp.email_tool import draft_advisor_email, EmailResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dispatch result
# ---------------------------------------------------------------------------

@dataclass
class MCPDispatchResult:
    """Aggregated result of all 3 MCP tool calls."""
    all_success: bool = False
    calendar_result: Optional[CalendarHoldResult] = None
    notes_result: Optional[NoteResult] = None
    email_result: Optional[EmailResult] = None
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------

def _retry_once(fn, *args, **kwargs):
    """Call fn once; if it fails, retry one more time."""
    result = fn(*args, **kwargs)
    if not result.success:
        logger.warning(f"MCP tool {fn.__name__} failed, retrying: {result.error}")
        result = fn(*args, **kwargs)
    return result


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

def execute_booking_side_effects(
    topic: str,
    code: str,
    date: str,
    time: str,
    waitlist: bool = False,
) -> MCPDispatchResult:
    """
    Execute all 3 MCP side effects for a confirmed booking.

    Called ONCE when user confirms a booking. Executes sequentially:
      1. Calendar → tentative hold
      2. Notes → append booking entry
      3. Email → draft advisor notification

    Args:
        topic:    Consultation topic name
        code:     Booking code
        date:     Formatted date string
        time:     Formatted time string
        waitlist: Whether this is a waitlist booking

    Returns:
        MCPDispatchResult with individual results and error list
    """
    result = MCPDispatchResult()
    slot_display = f"{time} IST"

    # ── Step 1: Calendar Hold ──
    cal_result = _retry_once(
        create_tentative_hold,
        topic=topic,
        code=code,
        date=date,
        time=time,
        waitlist=waitlist,
    )
    result.calendar_result = cal_result
    if not cal_result.success:
        result.errors.append(f"Calendar: {cal_result.error}")
        logger.error(f"Calendar hold failed for {code}: {cal_result.error}")

    # ── Step 2: Notes Append ──
    event_id = cal_result.event_id if cal_result.success else None
    status = "Waitlist" if waitlist else "Tentative"

    notes_result = _retry_once(
        append_booking_note,
        date=date,
        topic=topic,
        slot=slot_display,
        code=code,
        status=status,
        calendar_event_id=event_id,
    )
    result.notes_result = notes_result
    if not notes_result.success:
        result.errors.append(f"Notes: {notes_result.error}")
        logger.error(f"Notes append failed for {code}: {notes_result.error}")

    # ── Step 3: Email Draft ──
    email_result = _retry_once(
        draft_advisor_email,
        topic=topic,
        code=code,
        slot=slot_display,
        date=date,
        waitlist=waitlist,
    )
    result.email_result = email_result
    if not email_result.success:
        result.errors.append(f"Email: {email_result.error}")
        logger.error(f"Email draft failed for {code}: {email_result.error}")

    # ── Summary ──
    result.all_success = (
        cal_result.success and notes_result.success and email_result.success
    )

    if result.all_success:
        logger.info(f"All MCP side effects completed for {code}")
    else:
        logger.warning(f"Partial MCP failure for {code}: {result.errors}")

    return result


def execute_cancel_side_effects(
    event_id: str,
    code: str,
) -> MCPDispatchResult:
    """
    Execute MCP side effects for a cancellation.

    Args:
        event_id: Calendar event ID to cancel
        code:     Booking code

    Returns:
        MCPDispatchResult
    """
    result = MCPDispatchResult()

    # Cancel calendar hold
    cal_result = _retry_once(cancel_calendar_hold, event_id=event_id)
    result.calendar_result = cal_result
    if not cal_result.success:
        result.errors.append(f"Calendar cancel: {cal_result.error}")

    # Append cancellation note
    notes_result = _retry_once(
        append_booking_note,
        date="",
        topic="",
        slot="",
        code=code,
        status="Cancelled",
        calendar_event_id=event_id,
    )
    result.notes_result = notes_result
    if not notes_result.success:
        result.errors.append(f"Notes: {notes_result.error}")

    result.all_success = cal_result.success and notes_result.success
    return result
