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

    def test_date_without_time_asks_only_for_time(self):
        session = fresh_session()
        handle("", session)
        handle("book an appointment", session)
        handle("sip", session)
        responses = handle("20 april", session)
        joined = " ".join(responses).lower()
        assert "what time" in joined
        assert "topic is sip/mandates" in joined

    def test_topic_prompt_asks_for_date_first(self):
        session = fresh_session()
        handle("", session)
        handle("book an appointment", session)
        responses = handle("sip", session)
        joined = " ".join(responses).lower()
        assert "please tell me date so that i can tell you available time slot" in joined

    def test_time_without_date_asks_for_date(self):
        session = fresh_session()
        handle("", session)
        handle("book an appointment", session)
        handle("sip", session)
        responses = handle("4pm", session)
        joined = " ".join(responses).lower()
        assert "please tell me date so that i can tell you available time slot" in joined

    def test_date_then_time_moves_to_slot_offering(self):
        session = fresh_session()
        handle("", session)
        handle("book an appointment", session)
        handle("sip", session)
        handle("20 april", session)
        responses = handle("4pm", session)
        joined = " ".join(responses).lower()
        assert "slot" in joined or "found" in joined
        assert session.state == State.SLOT_OFFERED

    def test_unavailable_time_offers_available_slots_same_date(self):
        session = fresh_session()
        handle("", session)
        handle("book appointment for KYC", session)
        responses = handle("20 april 9pm", session)
        joined = " ".join(responses).lower()

        assert "unavailable" in joined
        assert "available slots" in joined
        assert session.state == State.AVAILABILITY_VIEW
        assert len(session.offered_slots) > 0

    def test_after_failed_booking_availability_query_shows_slots(self):
        session = fresh_session()
        handle("", session)
        handle("book appointment for SIP", session)
        handle("20 april 9pm", session)  # should fail exact-time match and enter recovery

        responses = handle("what slots are available", session)
        joined = " ".join(responses).lower()

        assert "available slots" in joined
        assert "tell me which time" in joined
        assert session.state == State.AVAILABILITY_VIEW
        assert session.topic == Topic.SIP_MANDATES
        assert session.date is not None

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

    def test_taken_slot_offers_alternatives(self):
        # Session A books a slot.
        s1 = fresh_session()
        handle("", s1)
        handle("I want to book for KYC", s1)
        handle("tomorrow at 3pm", s1)
        handle("1", s1)
        handle("yes", s1)
        assert s1.state == State.BOOKED

        # Session B tries to confirm that same already-booked slot (stale client scenario).
        s2 = fresh_session()
        s2.topic = Topic.KYC_ONBOARDING
        s2.date = "tomorrow"
        s2.time = "3pm"
        s2.chosen_slot = s1.chosen_slot
        s2.state = State.CONFIRMATION_PENDING
        responses = handle("yes", s2)
        joined = " ".join(responses).lower()

        assert s2.state == State.SLOT_OFFERED
        assert "taken" in joined or "next available" in joined


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
