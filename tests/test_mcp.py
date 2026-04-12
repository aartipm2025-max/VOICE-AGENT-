"""
Tests for Phase 4: MCP Tools and Dispatcher.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from mcp.calendar_tool import (
    create_tentative_hold, cancel_calendar_hold,
    get_event, reset_calendar_events
)
from mcp.notes_tool import (
    append_booking_note, get_note_by_code, reset_notes
)
from mcp.email_tool import (
    draft_advisor_email, get_draft, reset_drafts,
    DEFAULT_ADVISOR_EMAIL
)
from mcp.dispatcher import (
    execute_booking_side_effects, execute_cancel_side_effects
)


@pytest.fixture(autouse=True)
def setup_teardown():
    reset_calendar_events()
    reset_notes()
    reset_drafts()
    yield
    reset_calendar_events()
    reset_notes()
    reset_drafts()


class TestCalendarTool:

    def test_create_tentative_hold_success(self):
        res = create_tentative_hold("KYC", "NL-A742", "Monday", "10:30 AM")
        assert res.success is True
        assert res.event_id is not None

        event = get_event(res.event_id)
        assert event is not None
        assert event.status == "TENTATIVE"
        assert "NL-A742" in event.title

    def test_create_waitlist_hold(self):
        res = create_tentative_hold("KYC", "NL-A742", "Monday", "10:30 AM", waitlist=True)
        event = get_event(res.event_id)
        assert event.status == "TENTATIVE-WAITLIST"

    def test_cancel_hold(self):
        res = create_tentative_hold("KYC", "NL-A742", "Monday", "10:30 AM")
        cancel_res = cancel_calendar_hold(res.event_id)
        assert cancel_res.success is True

        event = get_event(res.event_id)
        assert event.status == "CANCELLED"


class TestNotesTool:

    def test_append_note_success(self):
        res = append_booking_note("2026-04-14", "SIP", "10:30 AM", "XY-Z123")
        assert res.success is True
        assert res.note_id is not None

        note = get_note_by_code("XY-Z123")
        assert note is not None
        assert note.topic == "SIP"
        assert note.status == "Tentative"

    def test_get_nonexistent_note_returns_none(self):
        assert get_note_by_code("FAKE") is None


class TestEmailTool:

    def test_draft_email_success(self):
        res = draft_advisor_email("Tax", "TX-111", "3:00 PM IST", "2026-04-14")
        assert res.success is True

        draft = get_draft(res.draft_id)
        assert draft is not None
        assert draft.approval_gated is True
        assert draft.status == "DRAFT"
        assert "Pre-Booking" in draft.subject
        assert draft.to == DEFAULT_ADVISOR_EMAIL

    def test_waitlist_email_variation(self):
        res = draft_advisor_email("Tax", "TX-111", "Any time", "Any day", waitlist=True)
        draft = get_draft(res.draft_id)
        assert draft.waitlist is True
        assert "WAITLIST" in draft.subject
        assert "Waitlist Request" in draft.body


class TestDispatcher:

    def test_execute_booking_all_success(self):
        result = execute_booking_side_effects(
            topic="KYC",
            code="AA-B111",
            date="Monday, 14 April 2026",
            time="10:30 AM",
            waitlist=False
        )

        assert result.all_success is True
        assert result.calendar_result.success is True
        assert result.notes_result.success is True
        assert result.email_result.success is True

        # Verify linkages
        event_id = result.calendar_result.event_id
        note = get_note_by_code("AA-B111")
        assert note is not None
        assert note.calendar_event_id == event_id

    def test_execute_booking_waitlist(self):
        result = execute_booking_side_effects(
            topic="SIP",
            code="WW-W222",
            date="Tuesday",
            time="Morning",
            waitlist=True
        )

        assert result.all_success is True

        event_id = result.calendar_result.event_id
        event = get_event(event_id)
        assert event.status == "TENTATIVE-WAITLIST"

        note = get_note_by_code("WW-W222")
        assert note.status == "Waitlist"

    def test_execute_cancel_success(self):
        # 1. Setup a booking
        book_res = execute_booking_side_effects("Tax", "CX-999", "Monday", "10:30 AM")
        event_id = book_res.calendar_result.event_id

        # 2. Cancel it
        cancel_res = execute_cancel_side_effects(event_id=event_id, code="CX-999")
        assert cancel_res.all_success is True

        # 3. Verify calendar updated
        event = get_event(event_id)
        assert event.status == "CANCELLED"

        # 4. Verify note appended
        # Getting the note by code should return the latest one? It returns the first matched.
        # But wait, execute_cancel appends a NEW note with status Cancelled.
        # Let's get the notes manually
        from mcp.notes_tool import get_all_notes
        notes = get_all_notes()
        cancelled_notes = [n for n in notes if n.code == "CX-999" and n.status == "Cancelled"]
        assert len(cancelled_notes) == 1
        assert cancelled_notes[0].calendar_event_id == event_id
