"""
nlp_engine.py
-------------
Sovereign Multilingual Conversational Pipeline (the "AI brain").

Pipeline:
  1. translate_to_english()   -> mocks Bhashini AI translation step
  2. extract_intent()         -> lightweight keyword-slot intent classifier
  3. analyze_caller_input()   -> full pipeline: translate -> sentiment -> normalized index

Run standalone to sanity check:
    python nlp_engine.py
"""
from __future__ import annotations

import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

import re
from deep_translator import GoogleTranslator

# ---------------------------------------------------------------------
# Step 2.1 — Mock Bhashini translation layer
# ---------------------------------------------------------------------
# In production this calls Bhashini's ASR + NMT pipeline (indic-conformer
# models). Here we use a small dictionary of common regional-language
# banking phrases -> English, standing in for that API call, backed by
# Google Translate (deep_translator) for anything not in the dictionary.
#
# LIMITATION: Google Translate's auto-detection is unreliable on
# *romanized* Indian-language text (Latin script, no diacritics) since
# there is no script signal to disambiguate the language. Native-script
# input (Devanagari, etc.) translates reliably; romanized input may
# silently pass through untranslated. This is a documented limitation
# of the mocked translation layer, not a bug in the surrounding pipeline.

_MOCK_TRANSLATION_DICT = {
    "मेरे खाते का बैलेंस बताओ": "tell me my account balance",
    "माझे एटीएम कार्ड ब्लॉक करा": "block my atm card",
    "मेरा कार्ड चोरी हो गया है": "my card has been stolen",
    "मुझे लोन चाहिए": "i need a loan",
    "पेंशन नहीं आई": "my pension has not arrived",
}


def translate_to_english(text: str, source_language: str = "auto") -> str:
    """Mocks the Bhashini AI speech/text translation step.

    Checks the small hardcoded dictionary first (guaranteed-correct demo
    phrases), then falls back to Google Translate with auto-detection.
    Any failure (network, unsupported language, silent pass-through)
    falls back to returning the original text unchanged, so the rest of
    the pipeline never crashes on a translation failure.
    """
    normalized = text.strip()
    if not normalized:
        return normalized

    if normalized in _MOCK_TRANSLATION_DICT:
        return _MOCK_TRANSLATION_DICT[normalized]

    try:
        result = GoogleTranslator(source="auto", target="en").translate(normalized)
        return result if result else normalized
    except Exception:
        return normalized


# ---------------------------------------------------------------------
# Step 2.2 — Intent classification & slot filling
# ---------------------------------------------------------------------

_INTENT_KEYWORDS = {
    # --- Order matters: more specific categories are checked before
    #     broader ones, so a narrower complaint isn't swallowed by a
    #     generic bucket lower down. ---------------------------------
    "Fraud": ["stolen", "block", "unauthorized", "fraud", "lost my wallet",
              "hacked", "compromised", "without my knowledge", "withdrew",
              "unknown transaction", "unknown charge", "don't recognize",
              "unrecognized transaction"],
    "Proactive Fraud Lock": ["did not authorize", "didn't authorize", "wasn't me",
              "not me", "did not make this transaction", "didn't make this payment",
              "i did not do this", "never made", "never authorized", "misuse",
              "lock my card", "suspicious"],
    "Balance Inquiry": ["balance", "account balance", "how much money",
              "transaction", "passbook", "statement"],
    "Video Banking Advisory": [
        "video call", "video banking", "wealth advisory", "mutual fund",
        "speak to a specialist", "speak to an advisor", "investment advice",
        "home loan planning",
    ],
    "Loans": ["loan", "emi", "interest rate", "disbursement", "loan application"],
    "Pension - Payment Delay": [
        "pension", "pensioner", "pension delay", "pension not credited",
        "pension not received",
    ],
    "General": [],
}


def extract_intent(english_text: str) -> dict:
    """Very lightweight keyword-based intent + slot extractor.
    Stands in for the production LLM-based intent classifier.
    """
    text_lower = english_text.lower()

    intent = "General"
    for candidate, keywords in _INTENT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            intent = candidate
            break

    # naive slot filling: pull out any account/card-like numeric sequences
    slots = {}
    numbers = re.findall(r"\b\d{4,}\b", english_text)
    if numbers:
        slots["account_or_card_number"] = numbers[0]

    return {"intent": intent, "slots": slots}


# ---------------------------------------------------------------------
# Step 2.3 — Sentiment inference (Hugging Face, with graceful fallback)
# ---------------------------------------------------------------------

_LABEL_TO_INDEX = {
    "Very Negative": -1.0,
    "Negative": -0.5,
    "Neutral": 0.0,
    "Positive": 0.5,
    "Very Positive": 1.0,
}

# Safety-net override: catches high-signal distress/fraud vocabulary the
# transformer model sometimes misreads as positive/neutral (e.g. polite
# phrasing like "please" alongside genuine distress). Includes a few
# romanized regional-language distress/help terms as a pragmatic stopgap
# for cases where the mocked translation layer leaves text untranslated.
_HIGH_CONFIDENCE_NEGATIVE_KEYWORDS = [
    "fraud", "unauthorized", "stolen", "scared", "panic", "urgent",
    "did not authorize", "didn't authorize", "never authorized",
    "block", "lock everything", "help", "scam", "misuse",
    # romanized regional-language distress/help terms
    "madad", "samjhatu nathi", "samajh nahi", "puriyala", "artham kadu",
    "pareshan", "dukh", "chinta",
]

_sentiment_model = None
_MODEL_LOAD_ATTEMPTED = False
_MODEL_LOAD_ERROR = None


def _load_model():
    """Lazily load the Hugging Face sentiment pipeline. Only attempted once."""
    global _sentiment_model, _MODEL_LOAD_ATTEMPTED, _MODEL_LOAD_ERROR
    if _MODEL_LOAD_ATTEMPTED:
        return
    _MODEL_LOAD_ATTEMPTED = True
    try:
        from transformers import pipeline
        _sentiment_model = pipeline(
            "text-classification",
            model="tabularisai/multilingual-sentiment-analysis",
        )
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any load failure -> fallback
        _MODEL_LOAD_ERROR = str(exc)
        _sentiment_model = None


def _rule_based_sentiment(text: str) -> tuple[str, float]:
    """Fallback scorer used only if the HF model can't be loaded
    (no internet / no cached weights). Keyword-weighted, not for production
    accuracy claims — just keeps the pipeline alive end-to-end.
    """
    text_lower = text.lower()
    very_neg_words = ["stolen", "fraud", "block everything", "gone", "panic", "urgent", "help"]
    neg_words = ["not arrived", "delay", "wrong", "issue", "problem", "block"]
    pos_words = ["thank", "great", "good", "resolved", "happy"]

    score = 0.0
    score -= 0.5 * sum(w in text_lower for w in very_neg_words)
    score -= 0.25 * sum(w in text_lower for w in neg_words)
    score += 0.4 * sum(w in text_lower for w in pos_words)
    score = max(-1.0, min(1.0, score))

    if score <= -0.75:
        label = "Very Negative"
    elif score < -0.15:
        label = "Negative"
    elif score < 0.15:
        label = "Neutral"
    elif score < 0.75:
        label = "Positive"
    else:
        label = "Very Positive"
    return label, score


def analyze_caller_input(text_input: str, source_language: str = "auto") -> dict:
    """Full pipeline entry point used by app.py.

    Returns:
        {
          "original_text": str,
          "translated_text": str,
          "intent": str,
          "slots": dict,
          "sentiment_label": str,
          "sentiment_score": float,   # raw HF probability (or fallback confidence)
          "emotional_index": float,   # normalized -1.0 .. +1.0
          "engine_used": "huggingface" | "fallback" | "...+keyword_override",
        }
    """
    translated = translate_to_english(text_input, source_language)
    intent_result = extract_intent(translated)

    _load_model()

    if _sentiment_model is not None:
        try:
            result = _sentiment_model(translated)[0]
            raw_label = result["label"]
            prob = float(result["score"])
            # model may return arbitrary label casing/format; normalize best-effort
            normalized_label = raw_label if raw_label in _LABEL_TO_INDEX else "Neutral"
            emotional_index = _LABEL_TO_INDEX[normalized_label] * prob
            engine_used = "huggingface"
            sentiment_label, sentiment_score = normalized_label, prob
        except Exception:  # noqa: BLE001
            sentiment_label, sentiment_score = _rule_based_sentiment(translated)
            emotional_index = _LABEL_TO_INDEX[sentiment_label]
            engine_used = "fallback"
    else:
        sentiment_label, sentiment_score = _rule_based_sentiment(translated)
        emotional_index = _LABEL_TO_INDEX[sentiment_label]
        engine_used = "fallback"

    # Safety-net override: high-signal distress/fraud keywords force a
    # negative reading even if the model scored it positive/neutral.
    text_lower = translated.lower()
    if any(kw in text_lower for kw in _HIGH_CONFIDENCE_NEGATIVE_KEYWORDS) and emotional_index > 0:
        emotional_index = min(emotional_index, -0.4)
        sentiment_label = "Negative"
        engine_used = engine_used + "+keyword_override"

    return {
        "original_text": text_input,
        "translated_text": translated,
        "intent": intent_result["intent"],
        "slots": intent_result["slots"],
        "sentiment_label": sentiment_label,
        "sentiment_score": round(sentiment_score, 3),
        "emotional_index": round(emotional_index, 3),
        "engine_used": engine_used,
    }


if __name__ == "__main__":
    samples = [
        "I want to lock my card immediately, I think someone is trying to misuse it right now!",
        "मेरे खाते का बैलेंस बताओ",
        "मेरा कार्ड चोरी हो गया है",
        "Thank you, my issue is resolved, great service.",
        "My pension has not been credited this month, please check",
        "I got a call saying I made a transaction but I did not authorize this at all",
        "I want to speak to a specialist about home loan planning and mutual funds",
        "Mari passbook ma je transaction dekhay che te mane samjhatu nathi, please madad karo",
    ]
    for s in samples:
        result = analyze_caller_input(s)
        print("-" * 70)
        print(f"IN:        {s}")
        print(f"Translated:{result['translated_text']}")
        print(f"Intent:    {result['intent']}  Slots: {result['slots']}")
        print(f"Sentiment: {result['sentiment_label']} "
              f"(score={result['sentiment_score']}, "
              f"emotional_index={result['emotional_index']}, "
              f"engine={result['engine_used']})")