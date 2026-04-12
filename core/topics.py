"""
Topic classification — Phase 2 LLM-powered, with keyword fallback.

Uses Google Gemini for structured topic resolution.
Falls back to keyword matching if LLM is unavailable.
"""

import os
from core.session import Topic
from core.prompts import TOPIC_CLASSIFICATION_PROMPT

# Reuse the same lazy LLM init pattern
_llm_client = None
_llm_available = None


def _get_llm_client():
    """Lazy-initialize Google Gemini client."""
    global _llm_client, _llm_available
    if _llm_available is not None:
        return _llm_client

    try:
        from google import genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            _llm_available = False
            return None
        _llm_client = genai.Client(api_key=api_key)
        _llm_available = True
        return _llm_client
    except (ImportError, Exception):
        _llm_available = False
        return None


# ---------------------------------------------------------------------------
# Keyword fallback (from Phase 1)
# ---------------------------------------------------------------------------

_TOPIC_KEYWORDS: dict[Topic, list[str]] = {
    Topic.KYC_ONBOARDING:          ["kyc", "onboarding", "verification",
                                     "identity"],
    Topic.SIP_MANDATES:            ["sip", "mandate", "systematic"],
    Topic.STATEMENTS_TAX_DOCS:     ["statement", "tax", "document", "docs"],
    Topic.WITHDRAWALS_TIMELINES:   ["withdraw", "withdrawal", "timeline",
                                     "redeem", "redemption"],
    Topic.ACCOUNT_CHANGES_NOMINEE: ["nominee", "nomination",
                                     "update account", "change account"],
}


def _keyword_fallback(text: str) -> Topic | None:
    """Phase 1 keyword-based topic detection as fallback."""
    text_lower = text.lower()
    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return topic
    return None


# ---------------------------------------------------------------------------
# LLM topic map
# ---------------------------------------------------------------------------

_LLM_TOPIC_MAP: dict[str, Topic] = {
    "1": Topic.KYC_ONBOARDING,
    "2": Topic.SIP_MANDATES,
    "3": Topic.STATEMENTS_TAX_DOCS,
    "4": Topic.WITHDRAWALS_TIMELINES,
    "5": Topic.ACCOUNT_CHANGES_NOMINEE,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_topic(user_text: str) -> Topic | None:
    """
    Classify user text into one of the 5 consultation topics.
    Returns None if the topic can't be determined.
    Uses LLM if available, falls back to keywords.
    """
    # Check number selection first (always works, no LLM needed)
    text_stripped = user_text.strip()
    if text_stripped in _LLM_TOPIC_MAP:
        return _LLM_TOPIC_MAP[text_stripped]

    client = _get_llm_client()

    if client is None:
        return _keyword_fallback(user_text)

    try:
        prompt = TOPIC_CLASSIFICATION_PROMPT.format(user_text=user_text)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        result = response.text.strip().lower()

        # LLM should return a number 1-5 or "unclear"
        if result in _LLM_TOPIC_MAP:
            return _LLM_TOPIC_MAP[result]

        if result == "unclear":
            return None

        # If LLM returned something unexpected, try keyword fallback
        return _keyword_fallback(user_text)

    except Exception:
        return _keyword_fallback(user_text)
