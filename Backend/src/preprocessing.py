"""
FILE: src/preprocessing.py
PURPOSE: Text Cleaning, Validation and Bilingual Support
VERSION: 3.0  |  GROUP: F25PROJECT664B0

The big change from v2: we now support bilingual input properly.
Previously, Urdu text was detected but then passed straight through to
TF-IDF which had never seen Urdu words, so predictions were random.

Now the approach is:
  1. Detect if the input contains Urdu characters
  2. If Urdu → skip English medical keyword validation entirely
     (the new dataset has Urdu training rows, so TF-IDF will match them)
  3. If English → run the existing medical validation as before
  4. Clean the text (lowercase, strip punctuation for English parts)

The validate_medical_text function is the main gatekeeper. It blocks:
  - Text that is too short (gibberish, single words)
  - Non-medical English text (greetings, random sentences)
  - Self-harm keywords (handled with care)
  - PII patterns (phone numbers, emails)

SRS: FR1, FR9 (bilingual support)
"""

import re
import logging

log = logging.getLogger(__name__)

# ── Urdu unicode range ─────────────────────────────────────────────────────────
# This is the standard range for Urdu/Arabic script characters.
_URDU_RANGE = re.compile(r'[\u0600-\u06FF]')

# ── Minimum symptom length ─────────────────────────────────────────────────────
MIN_SYMPTOM_LENGTH = 5

# ── Self-harm and crisis keywords — handled sensitively ───────────────────────
_SELF_HARM_KEYWORDS = {
    "suicide", "kill myself", "end my life", "self harm", "want to die",
    "خودکشی", "مرنا چاہتا ہوں", "زندگی ختم کرنا",
}

# ── PII patterns — block phone numbers and email addresses ────────────────────
_PII_PATTERNS = [
    re.compile(r'\b\d{10,11}\b'),              # phone numbers
    re.compile(r'[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+'),  # email addresses
    re.compile(r'\b(CNIC|cnic|passport)\s*\d+'),       # ID numbers
]

# ── English medical keyword set ────────────────────────────────────────────────
# The input does not need to contain ALL of these — just ONE is enough to
# pass validation. This list covers symptoms, body parts, and medical terms.
_MEDICAL_KEYWORDS = {
    # Symptoms — general
    "pain", "ache", "aching", "sore", "hurt", "hurts", "hurting",
    "fever", "temperature", "hot", "cold", "chill", "chills",
    "cough", "coughing", "sneeze", "sneezing", "wheeze", "wheezing",
    "breathless", "breathing", "breath", "shortness",
    "nausea", "vomit", "vomiting", "nauseous",
    "diarrhea", "diarrhoea", "constipation", "stool", "bowel",
    "headache", "head", "migraine",
    "dizzy", "dizziness", "lightheaded", "faint", "fainting",
    "fatigue", "tired", "tiredness", "exhausted", "weakness", "weak",
    "swelling", "swollen", "bloated", "bloating",
    "rash", "itching", "itchy", "scratch",
    "burning", "stinging",
    "numbness", "numb", "tingling",

    # Body parts
    "chest", "heart", "lung", "lungs", "stomach", "abdomen", "belly",
    "throat", "neck", "back", "spine", "shoulder", "arm", "leg",
    "knee", "ankle", "foot", "feet", "hand", "finger", "eye", "ear",
    "nose", "mouth", "tongue", "tooth", "teeth", "gum", "skin",
    "kidney", "liver", "bladder", "uterus", "joint", "joints",

    # Conditions / diseases
    "infection", "viral", "bacterial", "allergy", "allergic",
    "diabetes", "sugar", "blood pressure", "hypertension",
    "asthma", "pneumonia", "flu", "cold", "dengue", "typhoid",
    "malaria", "tuberculosis", "hepatitis", "cancer",
    "anxiety", "depression", "stress",
    "appendicitis", "gastritis", "arthritis",

    # Descriptors
    "severe", "mild", "moderate", "chronic", "acute", "sudden",
    "persistent", "continuous", "constant", "sharp", "dull",
    "throbbing", "radiating", "spreading",

    # Urination / bodily functions
    "urination", "urinating", "urine", "pee", "discharge",
    "period", "menstrual", "pregnancy", "pregnant",

    # Actions / states
    "bleeding", "blood", "sweat", "sweating", "shaking", "trembling",
    "loss of appetite", "appetite", "weight loss", "weight gain",
    "sleep", "insomnia", "restless",
}


def is_urdu(text: str) -> bool:
    """Returns True if the text contains Urdu/Arabic script characters."""
    return bool(_URDU_RANGE.search(text))


def clean_text(text: str) -> str:
    """
    Cleans and normalises the symptom text before it goes to the TF-IDF vectorizer.

    For English text: lowercases, removes special characters, collapses spaces.
    For Urdu text: preserves Urdu characters, just strips noise.
    Mixed text (English + Urdu): handles both safely.
    """
    if not text:
        return ""

    # Lowercase the English portion
    cleaned = text.lower()

    # Remove URLs
    cleaned = re.sub(r'http\S+|www\S+', '', cleaned)

    # Remove email addresses
    cleaned = re.sub(r'[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+', '', cleaned)

    # For English parts: remove special characters but preserve Urdu script
    # We keep: letters (any script), digits, spaces, common medical punctuation
    cleaned = re.sub(r'[^\w\s\u0600-\u06FF]', ' ', cleaned)

    # Collapse multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    return cleaned


def validate_medical_text(text: str) -> tuple:
    """
    Validates whether the input text is appropriate for medical prediction.

    Returns: (is_valid: bool, reason: str)

    The reason string is shown to the user if validation fails.
    """
    if not text or not text.strip():
        return False, "Please describe your symptoms before submitting."

    stripped = text.strip()

    # ── Minimum length check ──────────────────────────────────────────────
    if len(stripped) < MIN_SYMPTOM_LENGTH:
        return False, "Please describe your symptoms in more detail (at least a few words)."

    # ── Self-harm check — handled carefully ──────────────────────────────
    text_lower = stripped.lower()
    for keyword in _SELF_HARM_KEYWORDS:
        if keyword in text_lower:
            return False, (
                "It sounds like you may be going through something very difficult. "
                "Please reach out to a mental health professional or crisis helpline. "
                "In Pakistan you can call Umang helpline: 0317-4288665."
            )

    # ── PII check ─────────────────────────────────────────────────────────
    for pattern in _PII_PATTERNS:
        if pattern.search(stripped):
            return False, (
                "Please do not include personal information like phone numbers or emails. "
                "Describe only your symptoms."
            )

    # ── Urdu input: skip English keyword validation ───────────────────────
    # The new dataset has Urdu training rows for every disease.
    # TF-IDF will match Urdu words directly — no translation needed.
    if is_urdu(stripped):
        log.info("Urdu input detected — bypassing English keyword validation.")
        # Just check it has some minimum Urdu content
        urdu_chars = len(_URDU_RANGE.findall(stripped))
        if urdu_chars < 3:
            return False, "براہ کرم اپنی علامات تفصیل سے بیان کریں۔"
        return True, "ok"

    # ── English input: check for at least one medical keyword ─────────────
    words_in_text = set(text_lower.split())

    # Check for exact word matches
    has_medical_word = bool(words_in_text & _MEDICAL_KEYWORDS)

    # Also check for phrase matches (e.g. "blood pressure", "loss of appetite")
    if not has_medical_word:
        for keyword in _MEDICAL_KEYWORDS:
            if ' ' in keyword and keyword in text_lower:
                has_medical_word = True
                break

    if not has_medical_word:
        return False, (
            "Input lacks recognizable medical terms. "
            "Please describe your symptoms naturally — for example: "
            "'I have fever, headache and body pain for two days.'"
        )

    log.info("Medical validation passed.")
    return True, "ok"