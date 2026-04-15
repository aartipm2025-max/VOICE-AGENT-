"""
Tests for session management and FSM — aligned with refactored State enum.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.session import (
    Session, State, Intent, Topic, Slot,
    is_valid_transition, create_session, get_session,
    delete_session, clear_all_sessions,
)


@pytest.fixture(autouse=True)
def clean_store():
    clear_all_sessions()
    yield
    clear_all_sessions()


class TestSessionCreation:

    def test_new_session_has_uuid(self):
        s = Session()
        assert len(s.session_id) >= 32

    def test_initial_state_is_start(self):
        s = Session()
        assert s.state == State.START

    def test_disclaimer_not_given_initially(self):
        s = Session()
        assert s.disclaimer_given is False

    def test_no_topic_initially(self):
        s = Session()
        assert s.topic is None


class TestTurnLogging:

    def test_add_user_turn(self):
        s = Session()
        s.add_turn("user", "hello")
        assert len(s.turn_history) == 1
        assert s.turn_history[0].role == "user"

    def test_add_multiple_turns(self):
        s = Session()
        s.add_turn("user", "hello")
        s.add_turn("assistant", "hi")
        assert len(s.turn_history) == 2


class TestFSMTransitions:

    def test_start_to_topic_confirmed_is_valid(self):
        assert is_valid_transition(State.START, State.TOPIC_CONFIRMED)

    def test_start_to_ended_is_invalid(self):
        assert not is_valid_transition(State.START, State.ENDED)

    def test_start_to_cancel_flow_is_valid(self):
        assert is_valid_transition(State.START, State.CANCEL_FLOW)

    def test_topic_confirmed_to_slot_offered_is_valid(self):
        assert is_valid_transition(State.TOPIC_CONFIRMED, State.SLOT_OFFERED)

    def test_slot_offered_to_confirmation_pending_is_valid(self):
        assert is_valid_transition(State.SLOT_OFFERED, State.CONFIRMATION_PENDING)

    def test_confirmation_pending_to_booked_is_valid(self):
        assert is_valid_transition(State.CONFIRMATION_PENDING, State.BOOKED)

    def test_confirmation_pending_to_start_is_valid(self):
        assert is_valid_transition(State.CONFIRMATION_PENDING, State.START)

    def test_booked_to_ended_is_valid(self):
        assert is_valid_transition(State.BOOKED, State.ENDED)

    def test_ended_has_no_transitions(self):
        assert not is_valid_transition(State.ENDED, State.START)

    def test_session_transition_method(self):
        s = Session()
        assert s.state == State.START
        s.transition(State.TOPIC_CONFIRMED)
        assert s.state == State.TOPIC_CONFIRMED


class TestSessionStore:

    def test_create_and_retrieve(self):
        s = create_session()
        retrieved = get_session(s.session_id)
        assert retrieved is s

    def test_get_nonexistent_returns_none(self):
        assert get_session("nonexistent") is None

    def test_delete_session(self):
        s = create_session()
        assert delete_session(s.session_id) is True
        assert get_session(s.session_id) is None

    def test_delete_nonexistent_returns_false(self):
        assert delete_session("nonexistent") is False


class TestEnums:

    def test_all_5_intents(self):
        names = [i.value for i in Intent]
        assert "book_new" in names
        assert "cancel" in names

    def test_all_5_topics(self):
        assert len([t for t in Topic]) == 5

    def test_topic_values_readable(self):
        assert Topic.KYC_ONBOARDING.value == "KYC/Onboarding"
