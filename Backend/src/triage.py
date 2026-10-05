"""
FILE: src/triage.py
PURPOSE: Smart Triage Engine — Layered Disease Baseline + Symptom Escalation
VERSION: 3.0  |  GROUP: F25PROJECT664B0

Previous triage had two bugs:
1. Flat static lists — Food Poisoning was "Low" which is medically wrong.
   Dengue was "Medium" but dengue hemorrhagic fever kills people.
2. Confidence thresholds ran BEFORE disease checks, so Common Cold at
   82% confidence got "Urgent Care". That looked ridiculous in demos.

The new system works in layers:
  Layer 1: Check for red-flag emergency keywords in the raw text (always wins)
  Layer 2: Look up the disease's clinical baseline (Low / Medium / High)
  Layer 3: Check escalation keywords that can bump Medium → High
  Layer 4: Check de-escalation keywords that can drop Medium → Low
  Layer 5: Unknown diseases only → use confidence as fallback

This way, "Common Cold with difficulty breathing" → escalates to High.
And "Heart Attack" always stays High no matter what confidence score.

SRS: FR3, FR4, UC-01, UC-03
"""

import logging

log = logging.getLogger(__name__)


# ===========================================================================
# SPECIALIST ROUTING
# Maps each disease to the most appropriate type of doctor.
# ===========================================================================
SPECIALIST_MAP = {
    # Respiratory
    "Common Cold":          "General Physician",
    "Flu":                  "General Physician",
    "Pneumonia":            "Pulmonologist",
    "Asthma":               "Pulmonologist",
    "Tuberculosis":         "Pulmonologist",
    "Bronchitis":           "Pulmonologist",

    # Cardiovascular / Neurological
    "Heart Attack":         "Cardiologist",
    "Hypertension":         "Cardiologist",
    "Stroke":               "Neurologist",
    "Meningitis":           "Neurologist",

    # Gastrointestinal
    "Appendicitis":         "General Surgeon",
    "Gastritis":            "Gastroenterologist",
    "Food Poisoning":       "General Physician",
    "Hepatitis":            "Hepatologist",

    # Infectious / Tropical
    "Dengue Fever":         "Infectious Disease Specialist",
    "Typhoid":              "Infectious Disease Specialist",
    "Malaria":              "Infectious Disease Specialist",

    # Metabolic / Chronic
    "Diabetes":             "Endocrinologist",
    "Anemia":               "Hematologist",
    "Kidney Disease":       "Nephrologist",

    # Dermatological
    "Skin Allergy":         "Dermatologist",
    "Psoriasis":            "Dermatologist",
    "Shingles":             "Dermatologist",

    # ENT / Other
    "Tonsillitis":          "ENT Specialist",
    "Allergic Rhinitis":    "ENT Specialist",
    "Migraine":             "Neurologist",
    "Arthritis":            "Rheumatologist",

    # Mental Health
    "Depression":           "Psychiatrist",
    "Anxiety Disorder":     "Psychiatrist",

    # Urological
    "UTI":                  "Urologist",

    # Paediatric
    "Pediatric Fever":      "Paediatrician",

    # Musculoskeletal
    "Back Pain":            "Orthopaedic Specialist",
}


# ===========================================================================
# LAYER 1 — RED FLAG KEYWORDS
# If ANY of these appear in the patient's raw symptom text, we immediately
# return "High" regardless of what the model predicted.
# These are universally recognised emergency signals.
# ===========================================================================
_RED_FLAG_KEYWORDS = {
    # Cardiovascular
    "chest pain", "chest tightness", "chest pressure",
    "left arm pain", "jaw pain", "heart attack",
    "palpitations", "irregular heartbeat",

    # Neurological
    "loss of consciousness", "unconscious", "fainted",
    "seizure", "convulsion", "fits",
    "sudden confusion", "sudden weakness",
    "slurred speech", "facial drooping",
    "sudden severe headache", "worst headache",
    "neck stiffness", "photophobia",

    # Respiratory
    "cannot breathe", "can't breathe", "stopped breathing",
    "severe difficulty breathing", "gasping",
    "lips turning blue", "cyanosis",

    # Bleeding / Trauma
    "coughing blood", "vomiting blood", "blood in stool",
    "heavy bleeding", "internal bleeding",
    "black stool", "tarry stool",

    # Paediatric emergency
    "child not responding", "baby unconscious",
    "infant seizure", "high fever child not drinking",

    # Anaphylaxis
    "throat swelling", "throat closing", "anaphylaxis",
    "severe allergic reaction",

    # Urdu red flags
    "سینے میں شدید درد", "بے ہوشی", "دورہ", "فالج",
    "سانس نہیں آ رہا", "خون آ رہا ہے", "منہ سے خون",
}


# ===========================================================================
# LAYER 2 — DISEASE CLINICAL BASELINE
# Medically considered default severity for each predicted condition.
# This is NOT the final answer — layers 3 and 4 can modify it.
# ===========================================================================
_DISEASE_BASELINE = {
    # Always High — these are immediately life-threatening by nature
    "Heart Attack":         "High",
    "Stroke":               "High",
    "Meningitis":           "High",
    "Appendicitis":         "High",
    "Tuberculosis":         "High",
    "Malaria":              "High",

    # High defaults — serious but can be Medium if caught early and mild
    "Pneumonia":            "High",
    "Dengue Fever":         "High",
    "Typhoid":              "High",
    "Hepatitis":            "High",
    "Kidney Disease":       "High",

    # Medium defaults — need medical attention but not immediately life-threatening
    "Flu":                  "Medium",
    "Asthma":               "Medium",
    "Diabetes":             "Medium",
    "Hypertension":         "Medium",
    "Migraine":             "Medium",
    "Gastritis":            "Medium",
    "Anemia":               "Medium",
    "UTI":                  "Medium",
    "Tonsillitis":          "Medium",
    "Bronchitis":           "Medium",
    "Shingles":             "Medium",
    "Psoriasis":            "Medium",
    "Food Poisoning":       "Medium",
    "Skin Allergy":         "Medium",
    "Depression":           "Medium",
    "Anxiety Disorder":     "Medium",
    "Pediatric Fever":      "Medium",
    "Back Pain":            "Medium",
    "Arthritis":            "Medium",

    # Low defaults — manageable at home with rest and OTC remedies
    "Common Cold":          "Low",
    "Allergic Rhinitis":    "Low",
}


# ===========================================================================
# LAYER 3 — ESCALATION KEYWORDS
# If these appear alongside ANY disease, bump triage up one level.
# Medium → High. Low → Medium.
# ===========================================================================
_ESCALATION_KEYWORDS = {
    # Severity words
    "severe", "extreme", "unbearable", "excruciating",
    "worst ever", "cannot move", "cannot stand",
    "completely bedridden", "very high fever",

    # Respiratory distress
    "difficulty breathing", "shortness of breath", "breathless",
    "wheezing", "cannot breathe properly",

    # Neurological
    "confusion", "disoriented", "memory loss",
    "sudden vision loss", "blurred vision",

    # Systemic deterioration
    "not eating for days", "not drinking",
    "dehydrated", "severe dehydration",
    "rapid weight loss",

    # Paediatric
    "baby", "infant", "newborn",
    "child with high fever",

    # Urdu escalation
    "بہت شدید", "بے حد", "ناقابل برداشت",
    "سانس لینے میں مشکل", "بہت تیز بخار",
    "بچہ نہیں پی رہا",
}


# ===========================================================================
# LAYER 4 — DE-ESCALATION KEYWORDS
# If these appear alongside a High-baseline disease, we might bring it
# down to Medium if the symptoms sound mild.
# We are conservative here — only de-escalate if it's genuinely mild.
# Note: We never de-escalate below Medium. Safety first.
# ===========================================================================
_DE_ESCALATION_KEYWORDS = {
    "mild", "slight", "minor", "a little",
    "getting better", "improving",
    "only started today", "just started",
    "no fever", "no breathlessness",
    "ہلکا", "تھوڑا", "معمولی",
}


# ===========================================================================
# TRIAGE ACTIONS
# Human-readable guidance for each triage level.
# ===========================================================================
_TRIAGE_ACTIONS = {
    "High":   (
        "This may be an urgent medical situation. Please visit the nearest "
        "emergency room or call emergency services immediately. Do not wait."
    ),
    "Medium": (
        "You should see a doctor within 24-48 hours. Do not delay if symptoms "
        "worsen. Avoid self-medicating until you get a proper diagnosis."
    ),
    "Low":    (
        "Rest at home and stay hydrated. Monitor your symptoms. If they worsen "
        "or do not improve within 2-3 days, visit a General Physician."
    ),
}


# ===========================================================================
# MAIN: generate_triage()
# ===========================================================================

def generate_triage(
    disease: str,
    confidence: float,
    symptoms_cleaned: str,
) -> dict:
    """
    Runs all four layers to determine the correct triage level.

    Args:
        disease:          Top predicted disease name from classifier
        confidence:       Confidence score (0.0 to 1.0)
        symptoms_cleaned: The preprocessed symptom text

    Returns:
        dict with keys: triage_level, specialist, action
    """
    symptoms_lower = symptoms_cleaned.lower()
    specialist     = SPECIALIST_MAP.get(disease, "General Physician")

    # ── Layer 1: Red flags always win ──────────────────────────────────────
    for flag in _RED_FLAG_KEYWORDS:
        if flag in symptoms_lower:
            log.info(f"Red flag keyword '{flag}' detected → Urgent Care")
            return {
                "triage_level": "High",
                "specialist":   specialist,
                "action":       _TRIAGE_ACTIONS["High"],
            }

    # ── Layer 2: Disease clinical baseline ─────────────────────────────────
    baseline = _DISEASE_BASELINE.get(disease, None)

    if baseline is None:
        # Unknown disease — fall back to confidence thresholds
        if confidence >= 0.70:
            baseline = "High"
        elif confidence >= 0.40:
            baseline = "Medium"
        else:
            baseline = "Low"
        log.info(f"Unknown disease '{disease}', using confidence fallback → {baseline}")
    else:
        log.info(f"Disease '{disease}' has clinical baseline → {baseline}")

    # ── Layer 3: Escalation check ──────────────────────────────────────────
    escalation_triggered = any(kw in symptoms_lower for kw in _ESCALATION_KEYWORDS)

    if escalation_triggered:
        if baseline == "Low":
            baseline = "Medium"
            log.info("Escalation keywords found: Low → Medium")
        elif baseline == "Medium":
            baseline = "High"
            log.info("Escalation keywords found: Medium → High")
        # Already High — stays High

    # ── Layer 4: De-escalation check (conservative) ────────────────────────
    # We only allow de-escalation from High → Medium if disease is not
    # in the absolute-always-high group (Heart Attack, Stroke etc.)
    _ABSOLUTE_HIGH = {"Heart Attack", "Stroke", "Meningitis", "Appendicitis", "Tuberculosis", "Malaria"}

    if baseline == "High" and disease not in _ABSOLUTE_HIGH:
        de_escalation_triggered = any(kw in symptoms_lower for kw in _DE_ESCALATION_KEYWORDS)
        # Only de-escalate if NO escalation keyword was also present
        if de_escalation_triggered and not escalation_triggered:
            baseline = "Medium"
            log.info(f"De-escalation keywords found for '{disease}': High → Medium")

    return {
        "triage_level": baseline,
        "specialist":   specialist,
        "action":       _TRIAGE_ACTIONS[baseline],
    }


# ===========================================================================
# PERSONALIZED GUIDANCE — generate_personalized_guidance()
# Called by app.py after base triage to enrich with patient metadata.
# UC-03: Age, sex, severity, chronic disease, pregnancy.
# ===========================================================================

def generate_personalized_guidance(
    disease:          str,
    triage_level:     str,
    specialist:       str,
    age:              int   = None,
    sex:              str   = None,
    severity:         int   = None,   # 1–5 slider
    chronic_disease:  bool  = False,
    pregnant:         bool  = False,
    symptoms_cleaned: str   = "",
) -> dict:
    """
    Takes the base triage result and personalises it based on the
    patient metadata the user optionally provided in the UI panel.

    Returns an enriched dict with: triage_level, specialist, action,
    tips, profile_notes, red_flags.
    """
    profile_notes = []
    red_flags     = []
    tips          = _get_self_care_tips(disease)

    # ── Pregnancy escalation ───────────────────────────────────────────────
    if pregnant:
        profile_notes.append("Pregnancy noted — please consult an OB-GYN alongside any other specialist.")
        red_flags.append("Pregnant patients should avoid self-medicating. Some common drugs are unsafe during pregnancy.")
        # Always escalate to at least Medium for pregnant patients
        if triage_level == "Low":
            triage_level = "Medium"
            profile_notes.append("Triage upgraded to Visit GP because you are pregnant.")
        # Specialist override
        if specialist == "General Physician":
            specialist = "Obstetrician / General Physician"

    # ── Paediatric escalation (<12 years) ─────────────────────────────────
    if age is not None and age < 12:
        specialist = "Paediatrician"
        profile_notes.append(f"Age {age} detected — specialist changed to Paediatrician.")
        if triage_level == "Low":
            triage_level = "Medium"
            profile_notes.append("Children need earlier medical review. Triage upgraded.")

    # ── Elderly escalation (>65 years) ────────────────────────────────────
    if age is not None and age > 65:
        profile_notes.append(f"Age {age} detected — elderly patients may deteriorate faster.")
        red_flags.append("Elderly patients: if symptoms worsen overnight, go to emergency immediately.")
        if triage_level == "Low":
            triage_level = "Medium"
            profile_notes.append("Triage upgraded for elderly patient safety.")

    # ── Chronic disease escalation ─────────────────────────────────────────
    if chronic_disease:
        profile_notes.append("Chronic condition noted — your underlying health may worsen this illness.")
        red_flags.append("Patients with chronic diseases (diabetes, heart disease, etc.) are higher risk. See a doctor sooner.")
        if triage_level == "Low":
            triage_level = "Medium"

    # ── Severity slider escalation (4–5 out of 5) ─────────────────────────
    if severity is not None and severity >= 4:
        profile_notes.append(f"You rated severity {severity}/5 — this suggests significant discomfort.")
        if triage_level == "Low":
            triage_level = "Medium"
            profile_notes.append("Triage upgraded based on high self-reported severity.")
        elif triage_level == "Medium" and severity == 5:
            triage_level = "High"
            profile_notes.append("Maximum severity reported — upgraded to Urgent Care.")

    # ── Sex-specific notes ─────────────────────────────────────────────────
    if sex == "Female" and disease in {"UTI", "Kidney Disease"}:
        profile_notes.append("Women are more prone to UTIs. Make sure to stay hydrated and see a doctor promptly.")

    if sex == "Male" and disease == "Heart Attack":
        red_flags.append("Men over 45 are at higher risk for heart attacks. Do not delay emergency care.")

    # ── Final action text ──────────────────────────────────────────────────
    action = _TRIAGE_ACTIONS.get(triage_level, _TRIAGE_ACTIONS["Medium"])

    return {
        "triage_level":  triage_level,
        "specialist":    specialist,
        "action":        action,
        "tips":          tips,
        "profile_notes": profile_notes,
        "red_flags":     red_flags,
    }


# ===========================================================================
# SELF-CARE TIPS — per disease
# ===========================================================================

def _get_self_care_tips(disease: str) -> list:
    """Returns practical self-care tips for the predicted disease."""
    tips_map = {
        "Common Cold": [
            "Rest as much as possible and stay warm.",
            "Drink plenty of warm fluids — tea, soup, water.",
            "Use saline nasal drops to clear congestion.",
            "Paracetamol can help with fever and body aches.",
        ],
        "Flu": [
            "Rest completely and avoid contact with others.",
            "Drink at least 8-10 glasses of water or clear fluids daily.",
            "Paracetamol or ibuprofen can reduce fever.",
            "Seek medical help if fever exceeds 39°C or lasts more than 5 days.",
        ],
        "Pneumonia": [
            "Do NOT try to manage this at home — see a doctor immediately.",
            "Take prescribed antibiotics exactly as directed.",
            "Rest completely and avoid physical exertion.",
            "Monitor oxygen levels if you have a pulse oximeter.",
        ],
        "Asthma": [
            "Use your rescue inhaler as prescribed.",
            "Avoid triggers: dust, smoke, cold air, pets.",
            "Sit upright and stay calm during an episode.",
            "Go to emergency if the inhaler is not working within 15 minutes.",
        ],
        "Diabetes": [
            "Monitor your blood sugar levels regularly.",
            "Avoid sugary drinks and high-carb foods.",
            "Take your medication on time every day.",
            "Exercise lightly — a 30-minute walk helps glucose control.",
        ],
        "Hypertension": [
            "Reduce salt intake significantly.",
            "Avoid caffeine and alcohol.",
            "Take your blood pressure medication consistently.",
            "Check your BP at home and log it daily.",
        ],
        "Heart Attack": [
            "Call emergency services (1122 in Pakistan) immediately.",
            "Chew an aspirin (300mg) if available and not allergic.",
            "Sit or lie down quietly and stay calm.",
            "Do NOT drive yourself to hospital.",
        ],
        "Dengue Fever": [
            "Rest completely. Dengue is exhausting.",
            "Drink at least 3 litres of fluid daily — coconut water, ORS, juice.",
            "Take paracetamol ONLY — NO ibuprofen or aspirin (can cause bleeding).",
            "Monitor for bleeding gums or blood spots — go to hospital immediately.",
        ],
        "Food Poisoning": [
            "Drink ORS (oral rehydration salts) to replace lost fluids.",
            "Avoid solid food for 4-6 hours and then eat bland foods (toast, rice).",
            "Do NOT take anti-diarrheal medication without a doctor's advice.",
            "See a doctor if vomiting continues for more than 24 hours.",
        ],
        "UTI": [
            "Drink 2-3 litres of water daily to flush out bacteria.",
            "Avoid holding urine — urinate frequently.",
            "Avoid coffee and alcohol which irritate the bladder.",
            "See a doctor for antibiotics — UTIs rarely clear on their own.",
        ],
        "Migraine": [
            "Rest in a dark, quiet room.",
            "Apply a cold or warm compress to your forehead.",
            "Take your prescribed migraine medication at the first sign.",
            "Track triggers — stress, lack of sleep, and certain foods are common causes.",
        ],
        "Skin Allergy": [
            "Avoid scratching — it makes it worse and can cause infection.",
            "Use a gentle, fragrance-free moisturiser.",
            "Antihistamines (like cetirizine) can reduce itching.",
            "See a dermatologist if the rash does not improve in 3 days.",
        ],
        "Depression": [
            "Talk to someone you trust about how you are feeling.",
            "Maintain a light daily routine — small tasks help.",
            "Avoid alcohol — it worsens depression.",
            "Please see a doctor or psychiatrist. Depression is treatable.",
        ],
    }

    return tips_map.get(disease, [
        "Rest well and stay hydrated.",
        "Avoid self-medicating without a doctor's advice.",
        "Monitor your symptoms and seek medical care if they worsen.",
    ])