"""
FILE: src/clinical_guardrails.py
PURPOSE: Clinical Safety Guardrails: Negation Detection, OOV Detection, and Confidence Thresholding
AUTHOR: Antigravity / CS619 FYP Team
"""

import re
import logging
from typing import List, Tuple, Set, Iterable

log = logging.getLogger(__name__)

# ── Clause Boundary Patterns ──────────────────────────────────────────
# Negation scope terminates at punctuation or contrastive conjunctions
_BOUNDARY_PATTERN_EN = re.compile(
    r"[.,;!?\n]|"
    r"\b(but|however|although|except|yet|nevertheless|nonetheless|apart from|aside from)\b",
    re.IGNORECASE,
)

_BOUNDARY_PATTERN_UR = re.compile(
    r"[۔،؛!؟\n]|"
    r"\b(لیکن|مگر|تاہم|سوائے|البتہ)\b",
    re.UNICODE,
)

# ── English Negation Triggers ──────────────────────────────────────────
_PRE_NEGATION_EN = {
    "no", "not", "without", "denies", "denied", "denying",
    "negative for", "rules out", "ruled out", "free of",
    "no signs of", "no sign of", "no history of", "no evidence of",
    "never had", "neither", "nor", "not having", "not experiencing",
    "didn't have", "did not have", "does not have", "doesn't have",
    "haven't had", "have not had", "without any", "zero",
}

_POST_NEGATION_EN = {
    "was ruled out", "is ruled out", "is absent", "was absent",
    "is unlikely", "not present", "none",
}

# ── Urdu Negation Triggers ─────────────────────────────────────────────
# In Urdu, negation markers often appear directly before or after the symptom
_URDU_NEGATION_WORDS = {
    "نہیں", "نہیں ہے", "نہیں تھا", "نہیں تھی", "نہیں ہو رہا", "نہیں ہوتی", "کے بغیر", "کوئی نہیں",
}


def is_urdu_text(text: str) -> bool:
    """Checks if text contains Urdu/Arabic characters."""
    return bool(re.search(r"[\u0600-\u06FF]", text))


def _split_clauses(text: str, is_ur: bool = False) -> List[str]:
    """Splits text into independent linguistic clauses bounded by conjunctions or punctuation."""
    pattern = _BOUNDARY_PATTERN_UR if is_ur else _BOUNDARY_PATTERN_EN
    splits = pattern.split(text)
    # Filter out empty or delimiter match strings
    clauses = [s.strip() for s in splits if s and not pattern.fullmatch(s)]
    return clauses if clauses else [text.strip()]


def is_phrase_negated(phrase: str, text: str) -> bool:
    """
    Determines whether a clinical symptom/keyword phrase is negated within the surrounding text.
    Handles both English and Urdu syntactic structures.
    """
    phrase_clean = phrase.strip().lower()
    text_clean = text.strip()
    is_ur = is_urdu_text(text_clean)

    clauses = _split_clauses(text_clean, is_ur=is_ur)

    for clause in clauses:
        clause_lower = clause.lower()
        phrase_tokens = phrase_clean.split()
        clause_tokens = clause_lower.split()

        # Check whether the clause contains this phrase (exact or inflected)
        matches_clause = False
        if phrase_clean in clause_lower:
            matches_clause = True
        elif is_ur and len(phrase_tokens) >= 2:
            first_tok = phrase_tokens[0]
            stem_tok = phrase_tokens[1].rstrip("نانے")
            if any(first_tok in w for w in clause_tokens) and any(stem_tok in w for w in clause_tokens):
                matches_clause = True

        if not matches_clause:
            continue

        # Found the clause containing the phrase. Now inspect for negation triggers.
        if is_ur:
            # Urdu negation check within the bounded clause
            for neg in _URDU_NEGATION_WORDS:
                if neg in clause:
                    return True
        else:
            # English Negation syntax check
            words = clause_lower.split()
            phrase_tokens = phrase_clean.split()

            # Find starting index of phrase in tokens
            p_start = -1
            p_len = len(phrase_tokens)
            for i in range(len(words) - p_len + 1):
                if words[i:i + p_len] == phrase_tokens:
                    p_start = i
                    break

            if p_start != -1:
                # 1. Check Pre-negation (up to 5 tokens preceding the phrase)
                pre_window_tokens = words[max(0, p_start - 5):p_start]
                pre_window = " ".join(pre_window_tokens)
                for trigger in _PRE_NEGATION_EN:
                    # Match trigger as complete word sequence
                    pattern = rf"\b{re.escape(trigger)}\b"
                    if re.search(pattern, pre_window):
                        return True

                # 2. Check Post-negation (up to 4 tokens following the phrase)
                post_window_tokens = words[p_start + p_len:min(len(words), p_start + p_len + 5)]
                post_window = " ".join(post_window_tokens)
                for trigger in _POST_NEGATION_EN:
                    pattern = rf"\b{re.escape(trigger)}\b"
                    if re.search(pattern, post_window):
                        return True

    return False


def filter_affirmed_keywords(keywords: Iterable[str], text: str) -> List[str]:
    """
    Filters a set of clinical keywords against text, returning ONLY keywords that are
    affirmed (present and NOT negated).
    """
    text_lower = text.lower()
    affirmed = []

    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in text_lower:
            if not is_phrase_negated(kw_lower, text):
                affirmed.append(kw)
            else:
                log.info(f"Clinical Negation Guardrail: Negated keyword detected and ignored: '{kw}'")

    return affirmed


# ── OOV & Confidence Quality Evaluator ─────────────────────────────────

# Safety thresholds for 31-class multi-class classification
MIN_CONFIDENCE_THRESHOLD = 0.22  # Random guess is 1/31 = ~3.2%
MIN_FEATURE_OVERLAP_NNZ = 1      # Must have at least 1 non-zero TF-IDF feature
MIN_TFIDF_MASS = 0.08            # Sum of TF-IDF feature weights


def evaluate_prediction_confidence(
    X_vectorized,
    predictions: List[Tuple[str, float]],
) -> Tuple[bool, bool, str]:
    """
    Evaluates ML prediction quality against clinical safety boundaries.

    Returns:
        (is_oov: bool, is_low_confidence: bool, guidance_message: str)
    """
    # 1. Check vocabulary overlap
    nnz = X_vectorized.nnz if hasattr(X_vectorized, "nnz") else len(X_vectorized.nonzero()[0])
    tfidf_mass = float(X_vectorized.sum())

    if nnz < MIN_FEATURE_OVERLAP_NNZ or tfidf_mass < MIN_TFIDF_MASS:
        return (
            True,
            True,
            (
                "Your description did not match recognized clinical symptoms in our database. "
                "Please describe specific symptoms (e.g. location, duration, and severity of pain) "
                "or consult a doctor for a direct clinical evaluation."
            ),
        )

    # 2. Check model confidence score
    top_disease, top_conf = predictions[0]

    if top_conf < MIN_CONFIDENCE_THRESHOLD:
        return (
            False,
            True,
            (
                f"The symptoms match multiple possible conditions with low confidence "
                f"(top match: {top_disease} at {top_conf * 100:.0f}%). "
                f"We strongly recommend visiting a General Physician for an accurate clinical diagnosis."
            ),
        )

    return False, False, ""
