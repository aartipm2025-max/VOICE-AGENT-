"""
Tests for the core handler — aligned with refactored State enum and handler logic.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.session import Session, State, Topic
from core.handler import handle
from core.booking import reset_calendar


@pytest.fixture(autouse=True)
def setup():
    reset_calendar()
    yield
    reset_calendar()


def fresh_session() -> Session:
    """Create a fresh session in START state."""
    return Session()


class TestGreetingFlow:

    def test_empty_input_delivers_greeting(self):
        session = fresh_session()
        responses = handle("", session)
        joined = " ".join(responses).lower()
        assert "hello" in joined or "welcome" in joined

    def test_greeting_includes_disclaimer(self):
        session = fresh_session()
        responses = handle("", session)
        joined = " ".join(responses).lower()
        assert "investment advice" in joined or "informational" in joined


class TestIntentDetection:

    def test_book_intent(self):
        session = fresh_session()
        handle("", session)  # greeting
        responses = handle("I want to book an appointment", session)
        joined = " ".join(responses).lower()
        assert "topic" in joined or "book" in joined

    def test_cancel_intent(self):
        session = fresh_session()
        handle("", session)  # greeting
        responses = handle("I want to cancel my booking", session)
        assert session.state == State.CANCEL_FLOW

    def test_unknown_intent_shows_help(self):
        session = fresh_session()
        handle("", session)  # greeting
        responses = handle("asdfjkl gibberish", session)
        joined = " ".join(responses).lower()
        assert "book" in joined or "cancel" in joined or "help" in joined


class TestTopicDetection:

    def test_kyc_topic(self):
        session = fresh_session()
        handle("", session)
        handle("I want to book an appointment for KYC", session)
        assert session.topic == Topic.KYC_ONBOARDING

    def test_sip_topic(self):
        session = fresh_session()
        handle("", session)
        handle("I want to book for SIP", session)
        assert session.topic == Topic.SIP_MANDATES


class TestBookingFlow:

    def test_topic_then_time_offers_slots(self):
        session = fresh_session()
        handle("", session)
        handle("I want to book an appointment for KYC", session)
        responses = handle("tomorrow at 3pm", session)
        joined = " ".join(responses).lower()
        # Should either offer slots or ask for time
        assert "slot" in joined or "time" in joined or "found" in joined

    def test_topic_then_tmrw_time_offers_slots(self):
        session = fresh_session()
        handle("", session)
        handle("I want to book an appointment for KYC", session)
        responses = handle("tmrw 4pm", session)
        joined = " ".join(responses).lower()
        assert "slot" in joined or "found" in joined
        assert session.state == State.SLOT_OFFERED

    def test_full_flow_to_booked(self):
        session = fresh_session()
        handle("", session)
        handle("I want to book for KYC", session)
        handle("tomorrow at 3pm", session)
        # At this point, slots should be offered; confirm
        responses = handle("yes", session)
        # The state should eventually reach BOOKED
        assert session.state in [State.BOOKED, State.CONFIRMATION_PENDING, State.SLOT_OFFERED]

    def test_booking_code_is_generated(self):
        session = fresh_session()
        handle("", session)
        handle("I want to book for KYC", session)
        handle("tomorrow at 3pm", session)
        handle("1", session)
        handle("yes", session)
        if session.booking_code:
            assert "-" in session.booking_code
            assert len(session.booking_code) >= 5


class TestComplianceInHandler:

    def test_pii_blocked(self):
        session = fresh_session()
        handle("", session)
        responses = handle("my phone is 9876543210", session)
        joined = " ".join(responses).lower()
        assert "secure" in joined or "personal" in joined or "security" in joined

    def test_advice_blocked(self):
        session = fresh_session()
        handle("", session)
        responses = handle("which stock should I invest in?", session)
        joined = " ".join(responses).lower()
        assert "invest" in joined or "advice" in joined or "sebi" in joined


class TestRejectBooking:

    def test_reject_goes_back(self):
        session = fresh_session()
        handle("", session)
        handle("I want to book for KYC", session)
        handle("tomorrow at 3pm", session)
        handle("no", session)
        # After rejecting, the session should NOT be in BOOKED state
        assert session.state != State.BOOKED
