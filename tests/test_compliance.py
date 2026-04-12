"""
Tests for core/compliance.py — PII filter, advice refusal, disclaimer.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.compliance import (
    check_pii, PIICheckResult, PII_REJECTION_RESPONSE,
    check_advice_request, ADVICE_REFUSAL_RESPONSE,
    DISCLAIMER_TEXT,
)


# ── PII Detection ────────────────────────────────────────────────

class TestPIIDetection:

    def test_clean_text_no_pii(self):
        result = check_pii("I want to book an appointment for KYC")
        assert result.contains_pii is False

    def test_phone_number_10_digits(self):
        result = check_pii("My number is 9876543210")
        assert result.contains_pii is True
        assert result.pii_type == "personal information"  # matches phrase first

    def test_phone_number_pattern_only(self):
        result = check_pii("Call 9876543210 please")
        assert result.contains_pii is True

    def test_email_detected(self):
        result = check_pii("Send it to user@example.com")
        assert result.contains_pii is True

    def test_email_phrase(self):
        result = check_pii("my email is test@gmail.com")
        assert result.contains_pii is True
        assert result.pii_type == "personal information"

    def test_aadhaar_number(self):
        result = check_pii("My Aadhaar is 1234 5678 9012")
        assert result.contains_pii is True

    def test_pan_number(self):
        result = check_pii("PAN is ABCDE1234F")
        assert result.contains_pii is True
        assert result.pii_type == "PAN number"

    def test_account_number_long(self):
        result = check_pii("Account 123456789012345")
        assert result.contains_pii is True

    def test_pii_phrase_contact_me(self):
        result = check_pii("contact me at this address")
        assert result.contains_pii is True

    def test_sanitized_text(self):
        result = check_pii("Call 9876543210 for details")
        assert result.contains_pii is True
        if result.sanitized_text:
            assert "[REDACTED]" in result.sanitized_text

    def test_normal_numbers_not_flagged(self):
        """Short numbers like slot selections (1, 2) should not trigger PII."""
        result = check_pii("1")
        assert result.contains_pii is False

    def test_booking_code_not_flagged(self):
        """Booking codes like NL-A742 should not be flagged as PII."""
        result = check_pii("NL-A742")
        assert result.contains_pii is False

    def test_time_not_flagged(self):
        """Time strings should not be flagged."""
        result = check_pii("Monday at 3 PM")
        assert result.contains_pii is False


# ── Advice Refusal ────────────────────────────────────────────────

class TestAdviceRefusal:

    def test_stock_advice(self):
        assert check_advice_request("Which stock should I buy?") is True

    def test_invest_question(self):
        assert check_advice_request("Should I invest in mutual funds?") is True

    def test_best_fund(self):
        assert check_advice_request("What is the best mutual fund?") is True

    def test_portfolio_advice(self):
        assert check_advice_request("Can you give me portfolio advice?") is True

    def test_trading_tip(self):
        assert check_advice_request("Any trading tip for today?") is True

    def test_normal_booking_not_flagged(self):
        assert check_advice_request("I want to book an appointment") is False

    def test_topic_not_flagged(self):
        assert check_advice_request("I need help with KYC") is False

    def test_time_not_flagged(self):
        assert check_advice_request("Monday at 3 PM") is False

    def test_case_insensitive(self):
        assert check_advice_request("BEST MUTUAL FUND to buy?") is True


# ── Disclaimer ────────────────────────────────────────────────────

class TestDisclaimer:

    def test_disclaimer_contains_key_phrases(self):
        assert "informational" in DISCLAIMER_TEXT.lower()
        assert "investment advice" in DISCLAIMER_TEXT.lower()

    def test_pii_rejection_mentions_secure_link(self):
        assert "secure link" in PII_REJECTION_RESPONSE.lower()

    def test_advice_refusal_offers_alternative(self):
        assert "sebi" in ADVICE_REFUSAL_RESPONSE.lower() or \
               "educational" in ADVICE_REFUSAL_RESPONSE.lower()


# ── Integration: Compliance gates in handler ──────────────────────

class TestComplianceInHandler:
    """Test that compliance gates work within the full handle() flow."""

    def setup_method(self):
        from core.session import Session
        from core.handler import handle
        self.Session = Session
        self.handle = handle

    def _new_session_past_greeting(self):
        """Helper: create session and get past the greeting."""
        session = self.Session()
        self.handle("", session)  # trigger greeting
        return session

    def test_pii_blocked_during_intent(self):
        session = self._new_session_past_greeting()
        responses = self.handle("my email is test@gmail.com", session)
        assert any("secure link" in r.lower() for r in responses)
        # State should NOT change — PII rejection is a pass-through
        from core.session import State
        assert session.state == State.AWAIT_INTENT

    def test_advice_blocked_during_intent(self):
        session = self._new_session_past_greeting()
        responses = self.handle("Which stock should I buy?", session)
        assert any("not able to provide" in r.lower() or "investment" in r.lower()
                    for r in responses)
        from core.session import State
        assert session.state == State.AWAIT_INTENT

    def test_pii_blocked_during_topic_collection(self):
        session = self._new_session_past_greeting()
        self.handle("book appointment", session)
        responses = self.handle("my phone is 9876543210", session)
        assert any("secure link" in r.lower() for r in responses)
        from core.session import State
        assert session.state == State.COLLECT_TOPIC

    def test_clean_input_proceeds_normally(self):
        session = self._new_session_past_greeting()
        self.handle("book an appointment", session)
        from core.session import State
        assert session.state == State.COLLECT_TOPIC
