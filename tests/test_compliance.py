"""
Tests for compliance gates — PII detection, advice refusal, disclaimer.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.compliance import (
    check_pii, check_advice_request,
    PII_REJECTION_RESPONSE, ADVICE_REFUSAL_RESPONSE,
    DISCLAIMER_TEXT,
)
from core.session import Session, State
from core.handler import handle


class TestPIIDetection:

    def test_phone_number_10_digits(self):
        result = check_pii("Call me at 9876543210")
        assert result.contains_pii is True

    def test_phone_number_pattern_only(self):
        result = check_pii("9876543210")
        assert result.contains_pii is True

    def test_email_detected(self):
        result = check_pii("my email is user@example.com")
        assert result.contains_pii is True

    def test_email_phrase(self):
        result = check_pii("send it to test@gmail.com please")
        assert result.contains_pii is True

    def test_aadhaar_number(self):
        result = check_pii("My Aadhaar is 1234 5678 9012")
        assert result.contains_pii is True

    def test_pan_number(self):
        result = check_pii("My PAN is ABCDE1234F")
        assert result.contains_pii is True

    def test_account_number_long(self):
        result = check_pii("Account number 123456789012345")
        assert result.contains_pii is True

    def test_pii_phrase_contact_me(self):
        result = check_pii("contact me at this number")
        assert result.contains_pii is True

    def test_sanitized_text(self):
        result = check_pii("Call 9876543210 please")
        assert result.contains_pii is True
        if result.sanitized_text:
            assert "[REDACTED]" in result.sanitized_text

    def test_normal_numbers_not_flagged(self):
        result = check_pii("I want slot 1")
        assert result.contains_pii is False

    def test_booking_code_not_flagged(self):
        result = check_pii("My code is NL-A742")
        assert result.contains_pii is False

    def test_time_not_flagged(self):
        result = check_pii("3:00 PM tomorrow")
        assert result.contains_pii is False


class TestAdviceRefusal:

    def test_stock_advice(self):
        assert check_advice_request("which stock should I buy") is True

    def test_invest_question(self):
        assert check_advice_request("should I invest in mutual funds") is True

    def test_best_fund(self):
        assert check_advice_request("what is the best mutual fund") is True

    def test_portfolio_advice(self):
        assert check_advice_request("give me portfolio advice") is True

    def test_trading_tip(self):
        assert check_advice_request("Any trading tip?") is True

    def test_normal_booking_not_flagged(self):
        assert check_advice_request("I want to book an appointment") is False

    def test_topic_not_flagged(self):
        assert check_advice_request("I need help with KYC") is False

    def test_time_not_flagged(self):
        assert check_advice_request("Tomorrow at 3 PM") is False

    def test_case_insensitive(self):
        assert check_advice_request("WHICH STOCK should I buy") is True


class TestDisclaimer:

    def test_disclaimer_contains_key_phrases(self):
        assert "investment advice" in DISCLAIMER_TEXT.lower() or "informational" in DISCLAIMER_TEXT.lower()

    def test_pii_rejection_mentions_secure_link(self):
        assert "secure" in PII_REJECTION_RESPONSE.lower()

    def test_advice_refusal_offers_alternative(self):
        assert "sebi" in ADVICE_REFUSAL_RESPONSE.lower()


class TestComplianceInHandler:

    def test_pii_blocked_during_start(self):
        session = Session()
        handle("", session)  # greeting
        responses = handle("my phone is 9876543210", session)
        joined = " ".join(responses).lower()
        assert "secure" in joined or "personal" in joined

    def test_advice_blocked_during_start(self):
        session = Session()
        handle("", session)  # greeting
        responses = handle("should I invest in stocks?", session)
        joined = " ".join(responses).lower()
        assert "invest" in joined or "advice" in joined

    def test_clean_input_proceeds_normally(self):
        session = Session()
        handle("", session)  # greeting
        responses = handle("I want to book an appointment", session)
        joined = " ".join(responses).lower()
        assert "topic" in joined or "book" in joined
