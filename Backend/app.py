"""
FILE: app.py
PURPOSE: FastAPI Application Entry Point — AI-Powered Smart Health Assistant
VERSION: 2.0  |  GROUP: F25PROJECT664B0  |  SUPERVISOR: Shakeel Saeed

This is the main backend server for our project. Every single API call from
the React frontend lands here first before being handed off to the ML pipeline,
database, or PDF engine. Think of it as the traffic controller of the whole system.

SRS Coverage:
  UC-01  → /predict         (text symptom submission)
  UC-02  → /voice-input     (browser MediaRecorder blob → transcript)
  UC-02  → /predict         (voice transcript goes through same pipeline)
  UC-03  → /predict         (personalized guidance via metadata fields)
  UC-04  → /predict         (explainability features returned inline)
  UC-05  → /predict         (multilingual — language param forwarded)
  UC-06  → /history         (registered user history)
  UC-08  → /feedback        (1–5 star feedback loop)
  UC-07  → /admin/*         (admin analytics, user list, role management)
  UC-14  → /generate-pdf    (PDF export — accepts full data payload)

FR Requirements hit: FR1, FR2, FR3, FR4, FR6, FR7, FR8, FR10, FR11,
                     FR13, FR14, FR15, FR16, FR17, FR18
"""

import io
import os
# --- Robust FFmpeg Path Handling ---
# 1. Check if 'ffmpeg' is already accessible in the system PATH (Standard installation)
if not shutil.who("ffmpeg"):
    # 2. If not found, define the fallback developer path
    # NOTE: Evaluators should change this path if ffmpeg is not installed globally
    dev_ffmpeg_path = r"C:\Users\dmain\Downloads\ffmpeg-master-latest-win64-gpl\bin"
    
    if os.path.exists(dev_ffmpeg_path):
        os.environ["PATH"] += os.pathsep + dev_ffmpeg_path
        print(f"FFmpeg loaded from developer path: {dev_ffmpeg_path}")
    else:
        # 3. Fail-safe: Instead of crashing, we log a warning.
        # This allows the text-based AI to still work even if voice fails.
        print("CRITICAL WARNING: ffmpeg not found globally or in the developer path.")
        print("Voice-to-text functionality will be unavailable on this machine.")
# -----------------------------------

import logging
from fastapi import FastAPI, HTTPException, Response, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

# ── Core logic imports — each module handles one responsibility ────────────────
from src.preprocessing      import clean_text, validate_medical_text
from src.feature_extraction import load_vectorizer, transform_text
from src.classifier         import load_model, predict_top_k
from src.triage             import generate_triage, generate_personalized_guidance
from src.explainability     import get_top_features
from src.database import (
    init_db,
    save_consultation,
    fetch_history,
    login_user,
    register_user,
    save_feedback,
    get_analytics_summary,
    get_all_users_admin,
    update_user_role,
)
from src.pdf_generator import generate_pdf_from_data

# ── Logging — configured here once so all submodules inherit it ───────────────
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(
    title="AI-Powered Smart Health Assistant",
    version="2.0",
    description="Backend API for the FYP Health Assistant — Group F25PROJECT664B0",
)


# ===========================================================================
# CORS — allows our React dev server (port 5173) and any deployed origin
# In production you would lock this down to your actual domain.
# ===========================================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================================================
# TRIAGE LEVEL MAPPING
# The ML model → database uses "Low/Medium/High" (DB CHECK constraint).
# The frontend PredictionResponse type expects "self-care/visit-gp/urgent-care".
# This map bridges the two worlds so neither side needs to change.
# ===========================================================================
_TRIAGE_FRONTEND_MAP = {
    "Low":    "self-care",
    "Medium": "visit-gp",
    "High":   "urgent-care",
}

# The reverse map is needed when reading back from DB for history display.
_TRIAGE_DB_MAP = {v: k for k, v in _TRIAGE_FRONTEND_MAP.items()}


# ===========================================================================
# REQUEST / RESPONSE SCHEMAS
# Pydantic validates incoming JSON automatically — bad fields raise 422.
# ===========================================================================

class SymptomInput(BaseModel):
    """
    What the SymptomChecker.tsx sends us when the user hits 'Send'.
    The optional fields come from the patient metadata panel (UC-03).
    """
    symptoms: str
    language: Optional[str] = "en"
    user_id:  Optional[str] = None
    # UC-03 patient metadata — optional but improves personalisation
    age:             Optional[int]  = None
    sex:             Optional[str]  = None
    severity:        Optional[int]  = None   # 1–5 slider
    chronic_disease: Optional[bool] = False
    pregnant:        Optional[bool] = False


class AuthInput(BaseModel):
    """Login and registration share the same schema — full_name only used on sign-up."""
    email:     str
    password:  str
    full_name: Optional[str] = None


class FeedbackInput(BaseModel):
    """UC-08 feedback loop — 1–5 rating plus optional free-text comment."""
    consult_id: int
    rating:     int           # must be 1–5
    comments:   Optional[str] = None


class PdfRequest(BaseModel):
    """
    NEW in v2.0: instead of looking up the DB for PDF data (which could fail
    if the consult_id was never persisted), the frontend now sends us the
    full prediction payload so the PDF engine always has what it needs.
    """
    query_id:               str
    patient_name:           Optional[str] = "Patient"
    symptoms:               str
    conditions:             List[dict]
    triage_level:           str           # frontend format: "self-care" etc.
    triage_explanation:     Optional[str] = ""
    recommended_specialist: Optional[str] = "General Physician"
    key_symptoms:           Optional[List[str]] = []
    summary:                Optional[str] = ""


# ===========================================================================
# STARTUP
# ===========================================================================

@app.on_event("startup")
async def startup():
    # Make sure the DB tables exist before any request hits.
    # This is safe to call multiple times — uses IF NOT EXISTS internally.
    init_db()
    log.info("✅  Database initialized and ready.")


@app.get("/")
async def root():
    return {"message": "Health Assistant API v2.0 is running. Group: F25PROJECT664B0"}


# ===========================================================================
# VOICE INPUT — Browser Audio Blob Transcription  (UC-02)
# ===========================================================================
# WHY this exists:
#   Chrome's webkitSpeechRecognition sends audio to Google's servers from the
#   browser. On Pakistani networks those requests silently die — no error fires,
#   no result comes back, console just shows "undefined". That's the exact bug
#   we hit during testing.
#
# HOW this fixes it:
#   The browser records audio locally with MediaRecorder (no Google dependency),
#   then POSTs the blob HERE. We transcribe it server-side via speech_recognition
#   using a server-to-Google request, which works fine on our network.
#
# BEFORE USING — run once in your venv:
#   pip install SpeechRecognition pydub
#   winget install ffmpeg
# ===========================================================================

@app.post("/voice-input")
async def voice_input(
    audio: UploadFile = File(...),
    language: str = "en",
):
    """
    Accepts a raw audio blob from the browser MediaRecorder API.
    Transcribes it server-side using Google Speech Recognition.
    The network call happens from our server — not from the browser —
    so it bypasses whatever is blocking Chrome's SpeechRecognition on our ISP.

    Returns: { "transcript": "patient's symptoms as text", "language": "en-US" }
    """
    import speech_recognition as sr
    from pydub import AudioSegment

    # Map short lang codes to Google's locale strings
    lang_map = {
        "en":    "en-US",
        "ur":    "ur-PK",
        "en-US": "en-US",
        "ur-PK": "ur-PK",
    }
    google_lang = lang_map.get(language, "en-US")

    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio received.")

        log.info(f"Voice blob received: {len(audio_bytes)} bytes | lang={google_lang}")

        # Chrome MediaRecorder sends WebM, Firefox sends OGG.
        # pydub converts either format to WAV (16kHz mono) for speech_recognition.
        # ffmpeg must be installed for pydub to do the conversion.
        audio_io = io.BytesIO(audio_bytes)

        try:
            segment = AudioSegment.from_file(audio_io, format="webm")
        except Exception:
            try:
                audio_io.seek(0)
                segment = AudioSegment.from_file(audio_io, format="ogg")
            except Exception:
                audio_io.seek(0)
                segment = AudioSegment.from_file(audio_io)  # let pydub auto-detect

        # Convert to 16kHz mono WAV — optimal for Google Speech API
        wav_io = io.BytesIO()
        segment.set_frame_rate(16000).set_channels(1).export(wav_io, format="wav")
        wav_io.seek(0)

        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_data = recognizer.record(source)

        transcript = recognizer.recognize_google(audio_data, language=google_lang)

        if not transcript or len(transcript.strip()) < 3:
            raise HTTPException(
                status_code=422,
                detail="Transcription too short. Please speak more clearly."
            )

        log.info(f"Transcription OK: '{transcript[:80]}'")
        return {"transcript": transcript.strip(), "language": google_lang}

    except sr.UnknownValueError:
        # Audio reached Google but they couldn't decode speech from it
        raise HTTPException(
            status_code=422,
            detail="Could not understand the audio. Please speak clearly and try again."
        )
    except sr.RequestError as exc:
        # Server-side network issue — rare since server internet works fine
        log.error(f"Google Speech API unreachable: {exc}")
        raise HTTPException(
            status_code=503,
            detail="Speech service unavailable. Please type your symptoms instead."
        )
    except HTTPException:
        raise
    except Exception as exc:
        log.error(f"Voice input error: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Voice processing failed: {str(exc)}"
        )


# ===========================================================================
# CORE: SYMPTOM PREDICTION  (UC-01, UC-02, UC-03, UC-04)
# ===========================================================================

@app.post("/predict")
async def predict(data: SymptomInput):
    """
    The heart of the whole project. This endpoint:
    1. Validates the symptom input (blocks PII, non-medical text, too-short input)
    2. Runs preprocessing → feature extraction → ML classification
    3. Gets base triage recommendation
    4. Enriches triage with personalized guidance (age, sex, severity, risk flags)
    5. Extracts key symptoms via explainability module
    6. Saves to DB (or logs as guest session)
    7. Returns everything the frontend PredictionResponse type expects
    """
    # Basic guard — frontend also checks this but we validate server-side too
    if not data.symptoms or not data.symptoms.strip():
        raise HTTPException(status_code=400, detail="Symptoms cannot be empty.")

    # Step 1: Medical text validation — blocks gibberish, PII, self-harm keywords
    is_medical, reason = validate_medical_text(data.symptoms)
    if not is_medical:
        # Non-medical or unsafe input — return a structured error the UI can handle
        return {
            "error": "non_medical",
            "message": reason,
            "summary": reason,
            "conditions": [],
            "triage_level": "visit-gp",
            "triage_explanation": "",
            "recommended_specialist": "General Physician",
            "self_care_tips": [],
            "key_symptoms": [],
            "profile_notes": [],
            "red_flag_warnings": [],
            "disclaimer": "This assistant is not a substitute for professional medical advice.",
        }

    # Step 2: Clean and preprocess the raw text
    cleaned = clean_text(data.symptoms)

    # Step 3: ML Prediction — get top 3 probable conditions with confidence scores
    vectorizer  = load_vectorizer()
    model       = load_model()
    X           = transform_text(cleaned, vectorizer)
    predictions = predict_top_k(model, X, k=3)
    # predictions is a list of tuples: [(condition_name, confidence_score), ...]

    top_condition  = predictions[0][0]  # Index 0 is the condition name
    top_confidence = predictions[0][1]  # Index 1 is the probability

    # Step 4: Base triage (Low/Medium/High) + specialist from rule engine
    base_triage = generate_triage(top_condition, top_confidence, cleaned)

    # Step 5: Personalized guidance enrichment (UC-03)
    # This upgrades triage for pregnant patients, adds pediatrician for children,
    # adds severity-based escalation, and injects risk-flag tips.
    personalized = generate_personalized_guidance(
        disease          = top_condition,
        triage_level     = base_triage["triage_level"],
        specialist       = base_triage["specialist"],
        age              = data.age,
        sex              = data.sex,
        severity         = data.severity,
        chronic_disease  = data.chronic_disease or False,
        pregnant         = data.pregnant or False,
        symptoms_cleaned = cleaned,
    )

    # Step 6: Explainability — extract the actual keywords that drove the prediction
    raw_features = get_top_features(model, vectorizer, X)
    # get_top_features returns [(word, score), ...] — we only need the words for the UI
    key_symptoms = [word for word, _score in raw_features] if raw_features else []

    # Step 7: Map triage level from DB format (Low/Medium/High) to frontend format
    db_triage_level = personalized.get("triage_level", base_triage["triage_level"])
    frontend_triage = _TRIAGE_FRONTEND_MAP.get(db_triage_level, "visit-gp")

    # Step 8: Persist to DB
    # We store the DB-format triage level (Low/Medium/High) to satisfy the CHECK constraint.
    query_id = save_consultation(
        symptoms   = data.symptoms,
        prediction = top_condition,
        triage     = db_triage_level,
        specialist = personalized.get("specialist", base_triage["specialist"]),
        user_id    = data.user_id,
    )

    # Build the disclaimer string inline (SRS FR10 — must appear on every result)
    disclaimer = (
        "This is AI-generated guidance only and NOT a medical diagnosis. "
        "Please consult a qualified doctor before making health decisions."
    )

    # Step 9: Return the full PredictionResponse the frontend is expecting
    # Convert tuples into a list of dictionaries so the UI can read them
    formatted_conditions = [
        {"name": name, "confidence": int(score * 100)}
        for name, score in predictions
    ]

    return {
        "query_id":               str(query_id),
        "conditions":             formatted_conditions,
        "triage_level":           frontend_triage,
        "triage_explanation":     personalized.get("action", base_triage.get("action", "")),
        "recommended_specialist": personalized.get("specialist", base_triage["specialist"]),
        "self_care_tips":         personalized.get("tips", []),
        "key_symptoms":           key_symptoms,
        "profile_notes":          personalized.get("profile_notes", []),
        "red_flag_warnings":      personalized.get("red_flags", []),
        "summary":                (
            f"Based on your symptoms, the most likely match is {top_condition} "
            f"with {top_confidence * 100:.0f}% confidence."
        ),
        "disclaimer": disclaimer,
    }


# ===========================================================================
# HISTORY — Registered Users Only  (UC-13)
# ===========================================================================

@app.get("/history")
async def history(user_id: str):
    """
    Returns the last 10 consultations for a logged-in user.
    The frontend Dashboard.tsx calls this on mount.
    We remap triage levels back to frontend format here too.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")

    # Handles both integer and prefixed string IDs like "patient-5"
    try:
        clean_id = user_id.strip()
        for prefix in ["patient-", "guest-", "admin-"]:
            if clean_id.startswith(prefix):
                clean_id = clean_id.replace(prefix, "")
        numeric_id = int(clean_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="user_id must be a number.")

    records = fetch_history(numeric_id)

    # Normalise the stored 'Low/Medium/High' triage to frontend format for display
    for r in records:
        if r.get("triage_level") in _TRIAGE_FRONTEND_MAP:
            r["triage_level"] = _TRIAGE_FRONTEND_MAP[r["triage_level"]]
        # Add fields the Dashboard expects
        r["ai_response"]          = f"Predicted: {r.get('prediction', '')}"
        r["predicted_conditions"] = None   # full conditions only in session, not persisted
        r["created_at"]           = r.get("timestamp", "")

    return records


# ===========================================================================
# AUTH — Login & Register  (UC-07, UC-08)
# ===========================================================================

@app.post("/auth/login")
async def login(data: AuthInput):
    """
    Authenticates a registered user.
    Returns the user object (without password hash) on success.
    """
    user = login_user(data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return user


@app.post("/auth/register")
async def register(data: AuthInput):
    """
    Creates a new patient account.
    The full_name field is required for registration.
    Returns 400 if the email is already registered.
    """
    if not data.full_name:
        raise HTTPException(status_code=400, detail="Full name is required for registration.")

    user = register_user(
        username = data.full_name,
        email    = data.email,
        password = data.password,
    )
    if not user:
        raise HTTPException(status_code=400, detail="Email already registered. Please log in.")
    return user


# ===========================================================================
# FEEDBACK LOOP  (UC-08)
# ===========================================================================

@app.post("/feedback")
async def submit_feedback(data: FeedbackInput):
    """
    UC-08: Saves a 1–5 star rating plus optional comment for a consultation.
    The frontend Explainability page has a star rating widget that calls this.
    This feeds into the admin analytics avg_rating metric.
    """
    if not (1 <= data.rating <= 5):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5.")

    try:
        feedback_id = save_feedback(
            consult_id = data.consult_id,
            rating     = data.rating,
            comments   = data.comments,
        )
        if feedback_id is None:
            raise HTTPException(status_code=409, detail="Feedback already submitted for this consultation.")
        return {"message": "Thanks for your feedback!", "feedback_id": feedback_id}
    except Exception as e:
        log.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail="Could not save feedback.")


# ===========================================================================
# PDF REPORT GENERATION  (UC-14)
# ===========================================================================

@app.post("/generate-pdf")
async def generate_pdf(data: PdfRequest):
    """
    UC-14: Generates a professional PDF health report.

    The frontend sends the full prediction payload so the PDF engine always
    has everything it needs — no DB lookup required, works for guests too.
    """
    try:
        # Convert frontend triage format back to the PDF engine's expected format
        pdf_triage = _TRIAGE_DB_MAP.get(data.triage_level, "Medium")

        pdf_data = {
            "query_id":               data.query_id,
            "patient_name":           data.patient_name or "Patient",
            "symptoms":               data.symptoms,
            "conditions":             data.conditions,
            "triage_level":           pdf_triage,
            "triage_explanation":     data.triage_explanation,
            "recommended_specialist": data.recommended_specialist,
            "key_symptoms":           data.key_symptoms,
            "summary":                data.summary,
            "generated_at":           __import__("datetime").datetime.now().isoformat(),
        }

        pdf_bytes = generate_pdf_from_data(pdf_data)

        if not pdf_bytes:
            raise HTTPException(status_code=500, detail="PDF generation returned empty content.")

        return Response(
            content    = pdf_bytes,
            media_type = "application/pdf",
            headers    = {
                "Content-Disposition": f"attachment; filename=health_report_{data.query_id}.pdf"
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"PDF generation error: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


# ===========================================================================
# ADMIN PANEL  (UC-07 — Analytics, User Management, Role Updates)
# ===========================================================================

# The admin secret is checked on every admin endpoint.
# In production this would be a proper JWT token check.
ADMIN_SECRET = "admin2025"


def _require_admin(token: str):
    """Simple token gate — called at the top of every admin route."""
    if token != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Admin access denied. Invalid token.")


@app.post("/admin/login")
async def admin_login(body: dict):
    """
    Admin login endpoint. Returns the token that frontend stores in localStorage
    and sends back in every subsequent admin API call as ?admin_key=...
    """
    if body.get("password") == ADMIN_SECRET:
        return {"token": ADMIN_SECRET, "role": "admin"}
    raise HTTPException(status_code=401, detail="Invalid admin credentials.")


@app.get("/admin/analytics")
async def admin_analytics(admin_key: str = "", token: str = ""):
    """
    Returns aggregated, anonymized analytics for the dashboard charts.
    Covers: triage distribution, top conditions, specialist demand,
            daily activity trend, avg feedback rating.
    No patient PII is exposed here — SRS Security requirement satisfied.
    """
    admin_key = admin_key or token
    _require_admin(admin_key)
    try:
        return get_analytics_summary()
    except Exception as e:
        log.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail="Analytics query failed.")


@app.get("/admin/users")
async def admin_users(admin_key: str = "", token: str = ""):
    """
    Returns anonymized user list for the admin panel.
    No passwords, no raw health data — just role, username, email, join date.
    """
    admin_key = admin_key or token
    _require_admin(admin_key)
    try:
        return get_all_users_admin()
    except Exception as e:
        log.error(f"Admin users error: {e}")
        raise HTTPException(status_code=500, detail="User query failed.")


@app.post("/admin/users/{user_id}/role")
async def admin_update_role(user_id: int, body: dict, admin_key: str = ""):
    """
    Allows the admin to promote or demote a user's role (Guest ↔ Patient).
    This is the RBAC requirement from the SRS security section.
    """
    _require_admin(admin_key)
    new_role = body.get("role", "")
    if not new_role:
        raise HTTPException(status_code=400, detail="Role field is required.")
    try:
        success = update_user_role(user_id, new_role)
        if not success:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found.")
        return {"message": f"User {user_id} role updated to '{new_role}' successfully."}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Role update error: {e}")
        raise HTTPException(status_code=500, detail="Role update failed.")