"""
Tests for core/session.py — Session, State FSM, and session store.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.session import (
    Session, State, Intent, Topic, Slot,
    is_valid_transition,
    create_session, get_session, delete_session,
    clear_all_sessions,
)


# ── Session creation ──────────────────────────────────────────────

class TestSessionCreation:

    def test_new_session_has_uuid(self):
        s = Session()
        assert s.session_id is not None
        assert len(s.session_id) == 36  # UUID format

    def test_initial_state_is_greeting(self):
        s = Session()
        assert s.state == State.GREETING

    def test_disclaimer_not_given_initially(self):
        s = Session()
        assert s.disclaimer_given is False

    def test_no_topic_initially(self):
        s = Session()
        assert s.topic is None


# ── Turn logging ──────────────────────────────────────────────────

class TestTurnLogging:

    def test_add_user_turn(self):
        s = Session()
        s.add_turn("user", "hello")
        assert len(s.turn_history) == 1
        assert s.turn_history[0].role == "user"
        assert s.turn_history[0].text == "hello"

    def test_add_multiple_turns(self):
        s = Session()
        s.add_turn("user", "hi")
        s.add_turn("assistant", "hello!")
        assert len(s.turn_history) == 2


# ── FSM transitions ──────────────────────────────────────────────

class TestFSMTransitions:

    def test_greeting_to_disclaimer_is_valid(self):
        assert is_valid_transition(State.GREETING, State.DISCLAIMER_DELIVERED)

    def test_greeting_to_ended_is_invalid(self):
        assert not is_valid_transition(State.GREETING, State.ENDED)

    def test_await_intent_to_collect_topic_is_valid(self):
        assert is_valid_transition(State.AWAIT_INTENT, State.COLLECT_TOPIC)

    def test_await_intent_to_confirm_cancel_is_valid(self):
        assert is_valid_transition(State.AWAIT_INTENT, State.CONFIRM_CANCEL)

    def test_offer_slots_to_confirm_booking_is_valid(self):
        assert is_valid_transition(State.OFFER_SLOTS, State.CONFIRM_BOOKING)

    def test_offer_slots_to_waitlist_is_valid(self):
        assert is_valid_transition(State.OFFER_SLOTS, State.WAITLIST)

    def test_confirm_booking_to_mcp_is_valid(self):
        assert is_valid_transition(State.CONFIRM_BOOKING, State.MCP_SIDE_EFFECTS)

    def test_mcp_to_handoff_is_valid(self):
        assert is_valid_transition(State.MCP_SIDE_EFFECTS, State.HANDOFF)

    def test_ended_has_no_transitions(self):
        assert not is_valid_transition(State.ENDED, State.GREETING)

    def test_session_transition_method(self):
        s = Session()
        s.transition(State.DISCLAIMER_DELIVERED)
        assert s.state == State.DISCLAIMER_DELIVERED


# ── Session store ─────────────────────────────────────────────────

class TestSessionStore:

    def setup_method(self):
        clear_all_sessions()

    def test_create_and_retrieve(self):
        s = create_session()
        retrieved = get_session(s.session_id)
        assert retrieved is s

    def test_get_nonexistent_returns_none(self):
        assert get_session("fake-id") is None

    def test_delete_session(self):
        s = create_session()
        assert delete_session(s.session_id) is True
        assert get_session(s.session_id) is None

    def test_delete_nonexistent_returns_false(self):
        assert delete_session("fake-id") is False


# ── Enums ─────────────────────────────────────────────────────────

class TestEnums:

    def test_all_5_intents(self):
        # 5 real intents + UNKNOWN
        assert len(Intent) == 6

    def test_all_5_topics(self):
        assert len(Topic) == 5

    def test_topic_values_readable(self):
        assert Topic.KYC_ONBOARDING.value == "KYC/Onboarding"
        assert Topic.SIP_MANDATES.value == "SIP/Mandates"
