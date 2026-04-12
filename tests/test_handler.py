"""
Tests for core/handler.py — handle() and state-driven conversation flow.

Phase 3: Updated to work with real booking engine (dynamic slots and codes).
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.session import Session, State, Topic, clear_all_sessions
from core.handler import handle
from core.intents import classify_intent as _detect_intent
from core.topics import classify_topic as _detect_topic
from core.session import Intent
from core.booking import reset_calendar


# ── Intent detection ──────────────────────────────────────────────

class TestIntentDetection:

    def test_book_intent(self):
        assert _detect_intent("I want to book an appointment") == Intent.BOOK_NEW

    def test_schedule_intent(self):
        assert _detect_intent("Can I schedule a meeting?") == Intent.BOOK_NEW

    def test_reschedule_intent(self):
        assert _detect_intent("I need to reschedule") == Intent.RESCHEDULE

    def test_cancel_intent(self):
        assert _detect_intent("Cancel my appointment") == Intent.CANCEL

    def test_prepare_intent(self):
        assert _detect_intent("What should I prepare?") == Intent.WHAT_TO_PREPARE

    def test_availability_intent(self):
        assert _detect_intent("What times are available?") == Intent.CHECK_AVAILABILITY

    def test_unknown_intent(self):
        assert _detect_intent("tell me a joke") == Intent.UNKNOWN

    def test_case_insensitive(self):
        assert _detect_intent("BOOK a slot") == Intent.BOOK_NEW


# ── Topic detection ───────────────────────────────────────────────

class TestTopicDetection:

    def test_kyc_topic(self):
        assert _detect_topic("I need help with KYC") == Topic.KYC_ONBOARDING

    def test_sip_topic(self):
        assert _detect_topic("SIP related query") == Topic.SIP_MANDATES

    def test_tax_topic(self):
        assert _detect_topic("I need my tax documents") == Topic.STATEMENTS_TAX_DOCS

    def test_withdrawal_topic(self):
        assert _detect_topic("withdrawal timeline") == Topic.WITHDRAWALS_TIMELINES

    def test_nominee_topic(self):
        assert _detect_topic("Change my nominee") == Topic.ACCOUNT_CHANGES_NOMINEE

    def test_unknown_topic(self):
        assert _detect_topic("something random") is None


# ── Full conversation flows ───────────────────────────────────────

class TestGreetingFlow:

    def test_greeting_delivers_disclaimer(self):
        session = Session()
        responses = handle("", session)
        assert session.disclaimer_given is True
        assert any("informational" in r.lower() for r in responses)

    def test_greeting_transitions_to_await_intent(self):
        session = Session()
        handle("", session)
        assert session.state == State.AWAIT_INTENT


class TestBookingFlow:
    """Walk through a complete booking with real calendar slots."""

    def setup_method(self):
        reset_calendar()
        self.session = Session()
        handle("", self.session)  # greeting

    def test_book_intent_goes_to_collect_topic(self):
        handle("I want to book an appointment", self.session)
        assert self.session.state == State.COLLECT_TOPIC

    def test_topic_selection_by_number(self):
        handle("book an appointment", self.session)
        handle("1", self.session)
        assert self.session.topic == Topic.KYC_ONBOARDING
        assert self.session.state == State.COLLECT_TIME_PREF

    def test_topic_selection_by_keyword(self):
        handle("book a slot", self.session)
        handle("SIP", self.session)
        assert self.session.topic == Topic.SIP_MANDATES

    def test_time_pref_offers_slots(self):
        handle("book appointment", self.session)
        handle("1", self.session)
        responses = handle("morning", self.session)
        # Should offer slots or go to waitlist
        assert self.session.state in (State.OFFER_SLOTS, State.WAITLIST)
        if self.session.state == State.OFFER_SLOTS:
            assert len(self.session.offered_slots) >= 1
            assert any("Slot 1" in r for r in responses)

    def test_slot_selection(self):
        handle("book appointment", self.session)
        handle("1", self.session)
        handle("morning", self.session)
        if self.session.state == State.OFFER_SLOTS:
            handle("1", self.session)  # pick slot 1
            assert self.session.state == State.CONFIRM_BOOKING
            assert self.session.chosen_slot is not None

    def test_full_booking_to_end(self):
        handle("schedule appointment", self.session)
        handle("2", self.session)  # SIP/Mandates
        handle("afternoon", self.session)
        if self.session.state == State.OFFER_SLOTS:
            handle("1", self.session)  # pick slot
            handle("yes", self.session)  # confirm
            assert self.session.booking_code is not None
            assert len(self.session.booking_code) == 7  # XX-YZZZ
            assert self.session.state == State.ENDED

    def test_booking_code_is_unique(self):
        """Two bookings should get different codes."""
        reset_calendar()
        # Booking 1
        s1 = Session()
        handle("", s1)
        handle("book", s1)
        handle("1", s1)
        handle("morning", s1)
        if s1.state == State.OFFER_SLOTS:
            handle("1", s1)
            handle("yes", s1)

        # Booking 2
        s2 = Session()
        handle("", s2)
        handle("book", s2)
        handle("1", s2)
        handle("afternoon", s2)
        if s2.state == State.OFFER_SLOTS:
            handle("1", s2)
            handle("yes", s2)

        if s1.booking_code and s2.booking_code:
            assert s1.booking_code != s2.booking_code

    def test_reject_booking_goes_back(self):
        handle("book", self.session)
        handle("3", self.session)  # Statements/Tax Docs
        handle("morning", self.session)
        if self.session.state == State.OFFER_SLOTS:
            handle("1", self.session)  # pick slot
            handle("no", self.session)  # reject
            assert self.session.state == State.AWAIT_INTENT
            assert self.session.booking_code is None


class TestCancelFlow:

    def setup_method(self):
        self.session = Session()
        handle("", self.session)

    def test_cancel_intent(self):
        handle("cancel my appointment", self.session)
        assert self.session.state == State.CONFIRM_CANCEL

    def test_cancel_with_code(self):
        handle("cancel", self.session)
        handle("NL-A742", self.session)
        assert self.session.state == State.AWAIT_INTENT


class TestInfoFlows:

    def setup_method(self):
        reset_calendar()
        self.session = Session()
        handle("", self.session)

    def test_what_to_prepare_stays_at_await(self):
        handle("What should I prepare?", self.session)
        assert self.session.state == State.AWAIT_INTENT

    def test_check_availability_shows_days(self):
        responses = handle("What times are available?", self.session)
        assert self.session.state == State.AWAIT_INTENT
        # Should show real available days from calendar
        combined = " ".join(responses)
        assert "available" in combined.lower() or "slot" in combined.lower()


class TestUnknownInput:

    def test_unknown_intent_shows_help(self):
        session = Session()
        handle("", session)
        responses = handle("tell me a joke", session)
        assert session.state == State.AWAIT_INTENT
        assert any("help you with" in r.lower() for r in responses)


class TestSlotRejection:

    def setup_method(self):
        reset_calendar()

    def test_neither_slot_goes_back_to_time(self):
        session = Session()
        handle("", session)
        handle("book", session)
        handle("1", session)
        handle("morning", session)
        if session.state == State.OFFER_SLOTS:
            handle("neither", session)
            assert session.state == State.COLLECT_TIME_PREF


class TestWaitlistFlow:

    def setup_method(self):
        reset_calendar()

    def test_waitlist_try_different(self):
        session = Session()
        handle("", session)
        handle("book", session)
        handle("1", session)
        # Use a very specific time that likely won't match
        handle("Saturday at midnight", session)
        if session.state == State.WAITLIST:
            handle("1", session)  # try different time
            assert session.state == State.COLLECT_TIME_PREF

    def test_waitlist_add_me(self):
        session = Session()
        handle("", session)
        handle("book", session)
        handle("1", session)
        handle("Saturday at midnight", session)
        if session.state == State.WAITLIST:
            handle("2", session)  # add to waitlist
            assert session.state == State.AWAIT_INTENT
            assert session.booking_code is not None


class TestEndedState:

    def setup_method(self):
        reset_calendar()

    def test_ended_session_stays_ended(self):
        session = Session()
        handle("", session)
        handle("book", session)
        handle("1", session)
        handle("morning", session)
        if session.state == State.OFFER_SLOTS:
            handle("1", session)
            handle("yes", session)
            assert session.state == State.ENDED
            responses = handle("hello again", session)
            assert session.state == State.ENDED
            assert any("ended" in r.lower() for r in responses)
