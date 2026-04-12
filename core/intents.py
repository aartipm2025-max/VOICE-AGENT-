"""
Intent classification — Phase 2 LLM-powered, with keyword fallback.

Uses Google Gemini for structured intent classification.
Falls back to keyword matching if LLM is unavailable.
"""

import os
from core.session import Intent
from core.prompts import INTENT_CLASSIFICATION_PROMPT

# LLM client — lazy init
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
# Keyword fallback (from Phase 1 — kept as safety net)
# ---------------------------------------------------------------------------

_INTENT_KEYWORDS: list[tuple[Intent, list[str]]] = [
    (Intent.CANCEL,             ["cancel", "remove", "don't need", "delete"]),
    (Intent.RESCHEDULE,         ["reschedule", "change time", "move my",
                                 "different time", "shift"]),
    (Intent.WHAT_TO_PREPARE,    ["prepare", "bring", "need to have",
                                 "what should i"]),
    (Intent.CHECK_AVAILABILITY, ["available", "availability", "free slots",
                                 "open slots", "what times", "when can"]),
    (Intent.BOOK_NEW,           ["book", "schedule", "appointment", "new slot",
                                 "set up", "arrange"]),
]


def _keyword_fallback(text: str) -> Intent:
    """Phase 1 keyword-based intent detection as fallback."""
    text_lower = text.lower()
    for intent, keywords in _INTENT_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return intent
    return Intent.UNKNOWN


# ---------------------------------------------------------------------------
# LLM intent map
# ---------------------------------------------------------------------------

_LLM_INTENT_MAP: dict[str, Intent] = {
    "book_new":           Intent.BOOK_NEW,
    "reschedule":         Intent.RESCHEDULE,
    "cancel":             Intent.CANCEL,
    "what_to_prepare":    Intent.WHAT_TO_PREPARE,
    "check_availability": Intent.CHECK_AVAILABILITY,
    "unknown":            Intent.UNKNOWN,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_intent(user_text: str) -> Intent:
    """
    Classify user text into one of the 5 intents (or UNKNOWN).
    Uses LLM if available, falls back to keywords.
    """
    client = _get_llm_client()

    if client is None:
        return _keyword_fallback(user_text)

    try:
        prompt = INTENT_CLASSIFICATION_PROMPT.format(user_text=user_text)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        result = response.text.strip().lower()

        # Map LLM output to Intent enum
        intent = _LLM_INTENT_MAP.get(result, None)
        if intent is not None:
            return intent

        # If LLM returned something unexpected, try keyword fallback
        return _keyword_fallback(user_text)

    except Exception:
        return _keyword_fallback(user_text)
