"""
Compliance gates — run on every turn BEFORE intent handling.

Three gates:
  1. Disclaimer gate — auto-prepend disclaimer if not yet spoken.
  2. PII filter     — detect and reject personal data in user input.
  3. Advice refusal — refuse investment/financial advice requests.
"""

import re
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# PII detection patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("phone number",   re.compile(r"\b\d{10,12}\b")),
    ("email address",  re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    ("Aadhaar number", re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")),
    ("PAN number",     re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("account number", re.compile(r"\b\d{9,18}\b")),
]

# Phrases where user is explicitly trying to share PII
_PII_PHRASES: list[str] = [
    "my number is", "my email is", "my phone is",
    "my aadhaar", "my pan", "my account number",
    "contact me at", "reach me at", "call me at",
]


@dataclass
class PIICheckResult:
    """Result of PII scanning."""
    contains_pii: bool
    pii_type: str | None = None      # e.g. "phone number", "email address"
    sanitized_text: str | None = None  # user text with PII redacted


def check_pii(text: str) -> PIICheckResult:
    """
    Scan user text for PII patterns.
    Returns a result indicating whether PII was found, what type, and a
    sanitized version with matches replaced by [REDACTED].
    """
    # Check explicit PII-sharing phrases first
    text_lower = text.lower()
    for phrase in _PII_PHRASES:
        if phrase in text_lower:
            return PIICheckResult(
                contains_pii=True,
                pii_type="personal information",
                sanitized_text=None,
            )

    # Check regex patterns
    for pii_type, pattern in _PII_PATTERNS:
        if pattern.search(text):
            sanitized = pattern.sub("[REDACTED]", text)
            return PIICheckResult(
                contains_pii=True,
                pii_type=pii_type,
                sanitized_text=sanitized,
            )

    return PIICheckResult(contains_pii=False)


PII_REJECTION_RESPONSE = (
    "For your security, please do not share personal details like phone numbers, "
    "email addresses, or ID numbers on this call. I only need your consultation "
    "topic and preferred time. You'll receive a secure link to provide contact "
    "details after booking."
)


# ---------------------------------------------------------------------------
# Investment advice detection
# ---------------------------------------------------------------------------

_ADVICE_KEYWORDS: list[str] = [
    "which stock", "should i invest", "best mutual fund",
    "buy or sell", "market prediction", "stock tip",
    "recommend a fund", "portfolio advice", "investment advice",
    "which share", "where to invest", "financial advice",
    "best returns", "suggest a stock", "trading tip",
]


def check_advice_request(text: str) -> bool:
    """Return True if the user is asking for investment/financial advice."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in _ADVICE_KEYWORDS)


ADVICE_REFUSAL_RESPONSE = (
    "I'm not able to provide investment or financial advice. This service is "
    "strictly informational and helps you schedule advisor appointments. "
    "For educational resources on investing, please visit: "
    "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognised=yes "
    "\n\nIs there anything else I can help you with — such as booking, "
    "rescheduling, or cancelling an appointment?"
)


# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------

DISCLAIMER_TEXT = (
    "Please note: This is an informational service only — "
    "we do not provide investment advice. "
    "I can help you book, reschedule, or cancel an advisor appointment, "
    "check availability, or tell you what to prepare."
)
