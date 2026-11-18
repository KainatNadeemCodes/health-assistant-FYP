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
import shutil
import asyncio
import logging
from typing import List, Optional

# --- Robust FFmpeg Path Handling ---
# 1. Allow environment variable configuration if installed in non-standard location
custom_ffmpeg = os.getenv("FFMPEG_PATH")
if custom_ffmpeg and os.path.exists(custom_ffmpeg):
    os.environ["PATH"] += os.pathsep + custom_ffmpeg

# 2. Check if 'ffmpeg' is accessible in the system PATH
if not shutil.which("ffmpeg"):
    print("WARNING: ffmpeg not detected in PATH or FFMPEG_PATH.")
    print("Voice-to-text audio conversion may be unavailable unless ffmpeg is installed.")
# -----------------------------------

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Response, File, UploadFile, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Core logic imports — each module handles one responsibility ────────────────
from src.preprocessing      import clean_text, validate_medical_text
from src.feature_extraction import load_vectorizer, transform_text
from src.classifier         import load_model, predict_top_k
from src.triage             import generate_triage, generate_personalized_guidance
from src.explainability     import get_top_features
from src.clinical_guardrails import evaluate_prediction_confidence
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
from src.security import (
    create_access_token,
    get_current_user,
    get_current_user_optional,
    get_current_admin,
    ADMIN_SECRET,
)

# ── Logging — configured here once so all submodules inherit it ───────────────
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Hugging Face ZeroGPU Compatibility ─────────────────────────────────────────
try:
    import spaces

    @spaces.GPU
    def _zero_gpu_keepalive(text: str = ""):
        """Hugging Face ZeroGPU validator check."""
        return text
except Exception:
    pass


# ── Database Initialization ───────────────────────────────────────────────────
# Synchronous initialization guarantees compatibility across ASGI (Uvicorn) and WSGI (uWSGI / a2wsgi)
try:
    init_db()
    log.info("✅  Database initialized and ready.")
except Exception as e:
    log.error(f"Database initialization note: {e}")

app = FastAPI(
    title="AI-Powered Smart Health Assistant",
    version="2.0",
    description="Backend API for the FYP Health Assistant — Group F25PROJECT664B0",
)


# ===========================================================================
# CORS — Configurable allowed origins with secure defaults
# ===========================================================================
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")
origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],
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


@app.get("/")
def root():
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

def _transcode_and_transcribe_audio_worker(audio_bytes: bytes, google_lang: str) -> str:
    """
    Synchronous CPU/transcoding & network I/O worker.
    Offloaded to asyncio.to_thread pool to guarantee the FastAPI event loop is never blocked.
    """
    import speech_recognition as sr
    from pydub import AudioSegment

    audio_io = io.BytesIO(audio_bytes)
    try:
        segment = AudioSegment.from_file(audio_io, format="webm")
    except Exception:
        try:
            audio_io.seek(0)
            segment = AudioSegment.from_file(audio_io, format="ogg")
        except Exception:
            audio_io.seek(0)
            segment = AudioSegment.from_file(audio_io)  # auto-detect

    # Convert to 16kHz mono WAV — optimal for Google Speech API
    wav_io = io.BytesIO()
    segment.set_frame_rate(16000).set_channels(1).export(wav_io, format="wav")
    wav_io.seek(0)

    recognizer = sr.Recognizer()
    with sr.AudioFile(wav_io) as source:
        audio_data = recognizer.record(source)

    return recognizer.recognize_google(audio_data, language=google_lang)


@app.post("/voice-input")
async def voice_input(
    audio: UploadFile = File(...),
    language: str = "en",
):
    """
    Accepts a raw audio blob from the browser MediaRecorder API.
    Transcribes it asynchronously via a thread pool worker using Google Speech Recognition.
    Non-blocking: FastAPI remains fully responsive to other requests during transcoding and speech decoding.

    Returns: { "transcript": "patient's symptoms as text", "language": "en-US" }
    """
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

        # Offload CPU audio transcoding + speech API call to worker thread
        transcript = await asyncio.to_thread(
            _transcode_and_transcribe_audio_worker,
            audio_bytes,
            google_lang,
        )

        if not transcript or len(transcript.strip()) < 3:
            raise HTTPException(
                status_code=422,
                detail="Transcription too short. Please speak more clearly."
            )

        log.info(f"Transcription OK: '{transcript[:80]}'")
        return {"transcript": transcript.strip(), "language": google_lang}

    except HTTPException:
        raise
    except Exception as exc:
        exc_type = type(exc).__name__
        if exc_type == "UnknownValueError":
            # Audio reached Google but they couldn't decode speech from it
            raise HTTPException(
                status_code=422,
                detail="Could not understand the audio. Please speak clearly and try again."
            )
        elif exc_type == "RequestError":
            log.error(f"Google Speech API unreachable: {exc}")
            raise HTTPException(
                status_code=503,
                detail="Speech service unavailable. Please type your symptoms instead."
            )
        log.error(f"Voice input error: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Voice processing failed: {str(exc)}"
        )


# ===========================================================================
# CORE: SYMPTOM PREDICTION  (UC-01, UC-02, UC-03, UC-04)
# ===========================================================================

@app.post("/predict")
async def predict(
    data: SymptomInput,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
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

    # Step 3b: Clinical Safety Guardrail — Check OOV & Confidence Quality
    is_oov, is_low_conf, guard_message = evaluate_prediction_confidence(X, predictions)
    if is_oov:
        return {
            "error": "unrecognized_symptoms",
            "message": guard_message,
            "summary": guard_message,
            "conditions": [],
            "triage_level": "visit-gp",
            "triage_explanation": "Your description did not match recognized clinical patterns in our medical database.",
            "recommended_specialist": "General Physician",
            "self_care_tips": [
                "Track symptom frequency, onset, and triggers.",
                "Stay well hydrated and get adequate rest.",
                "Seek medical attention if your condition worsens.",
            ],
            "key_symptoms": [],
            "profile_notes": ["Clinical Note: Non-specific or unrecognized symptom presentation."],
            "red_flag_warnings": [],
            "disclaimer": "This assistant is not a substitute for professional medical advice.",
        }

    top_condition  = predictions[0][0]  # Index 0 is the condition name
    top_confidence = predictions[0][1]  # Index 1 is the probability

    # Step 4: Base triage (Low/Medium/High) + specialist from rule engine
    base_triage = generate_triage(top_condition, top_confidence, cleaned)

    # Step 5: Personalized guidance enrichment (UC-03)
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
    key_symptoms = [word for word, _score in raw_features] if raw_features else []

    # Step 7: Map triage level from DB format (Low/Medium/High) to frontend format
    db_triage_level = personalized.get("triage_level", base_triage["triage_level"])
    frontend_triage = _TRIAGE_FRONTEND_MAP.get(db_triage_level, "visit-gp")

    # Step 8: Persist to DB
    # Prioritize authenticated user from verified JWT over client-supplied user_id
    persisted_user_id = None
    if current_user and current_user.get("sub"):
        try:
            persisted_user_id = int(current_user["sub"])
        except ValueError:
            persisted_user_id = None
    elif data.user_id:
        try:
            persisted_user_id = int(str(data.user_id).replace("patient-", "").replace("guest-", ""))
        except ValueError:
            persisted_user_id = None

    query_id = save_consultation(
        symptoms   = data.symptoms,
        prediction = top_condition,
        triage     = db_triage_level,
        specialist = personalized.get("specialist", base_triage["specialist"]),
        user_id    = persisted_user_id,
    )

    # Build the disclaimer string inline (SRS FR10 — must appear on every result)
    disclaimer = (
        "This is AI-generated guidance only and NOT a medical diagnosis. "
        "Please consult a qualified doctor before making health decisions."
    )

    formatted_conditions = [
        {"name": name, "confidence": int(score * 100)}
        for name, score in predictions
    ]

    profile_notes = list(personalized.get("profile_notes", []))
    if is_low_conf:
        profile_notes.append("Clinical Warning: Non-specific symptom presentation. An in-person consultation is advised.")

    return {
        "query_id":               str(query_id),
        "conditions":             formatted_conditions,
        "triage_level":           frontend_triage,
        "triage_explanation":     personalized.get("action", base_triage.get("action", "")),
        "recommended_specialist": personalized.get("specialist", base_triage["specialist"]),
        "self_care_tips":         personalized.get("tips", []),
        "key_symptoms":           key_symptoms,
        "profile_notes":          profile_notes,
        "red_flag_warnings":      personalized.get("red_flags", []),
        "summary":                (
            f"Based on your symptoms, the most likely match is {top_condition} "
            f"with {top_confidence * 100:.0f}% confidence."
            + (" (Note: Ambiguous presentation — clinical evaluation strongly recommended.)" if is_low_conf else "")
        ),
        "disclaimer": disclaimer,
    }


# ===========================================================================
# HISTORY — Authenticated Users Only  (UC-13 — IDOR Protected)
# ===========================================================================

@app.get("/history")
async def history(
    user_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Returns the last 10 consultations for a logged-in user.
    Security: Resolves IDOR by enforcing that regular patients can ONLY access
    their own records based on their verified JWT sub claim.
    Admins may optionally supply a user_id to inspect patient history.
    """
    caller_role = str(current_user.get("role", "")).lower()
    caller_id = current_user.get("sub")

    if user_id and caller_role == "admin":
        target_id_str = user_id
    else:
        target_id_str = caller_id

    try:
        clean_id = str(target_id_str).strip()
        for prefix in ["patient-", "guest-", "admin-"]:
            if clean_id.startswith(prefix):
                clean_id = clean_id.replace(prefix, "")
        numeric_id = int(clean_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid user identification.")

    records = fetch_history(numeric_id)

    # Normalise stored triage levels
    for r in records:
        if r.get("triage_level") in _TRIAGE_FRONTEND_MAP:
            r["triage_level"] = _TRIAGE_FRONTEND_MAP[r["triage_level"]]
        r["ai_response"]          = f"Predicted: {r.get('prediction', '')}"
        r["predicted_conditions"] = None
        r["created_at"]           = r.get("timestamp", "")

    return records


# ===========================================================================
# AUTH — Login & Register  (UC-07, UC-08 — JWT Powered)
# ===========================================================================

@app.post("/auth/login")
async def login(data: AuthInput):
    """
    Authenticates a registered user.
    Returns user profile along with signed JWT access token.
    """
    user = login_user(data.email, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token({
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "username": user["username"],
    })

    return {
        **user,
        "access_token": token,
        "token_type": "bearer",
    }


@app.post("/auth/register")
async def register(data: AuthInput):
    """
    Creates a new patient account and returns user profile with JWT access token.
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

    token = create_access_token({
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "username": user["username"],
    })

    return {
        **user,
        "access_token": token,
        "token_type": "bearer",
    }


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

def _verify_admin_access(token: str = "", current_user: Optional[dict] = None):
    """
    Verifies admin access either via JWT claims (preferred) or legacy admin secret key.
    """
    if current_user and str(current_user.get("role", "")).lower() == "admin":
        return True
    if token and token == ADMIN_SECRET:
        return True
    raise HTTPException(status_code=403, detail="Admin access denied. Valid admin credentials or token required.")


@app.post("/admin/login")
async def admin_login(body: dict):
    """
    Admin login endpoint.
    Returns a cryptographically signed JWT with role='admin'.
    """
    if body.get("password") == ADMIN_SECRET:
        admin_jwt = create_access_token({
            "sub": "admin",
            "email": "admin@system.local",
            "role": "admin",
            "username": "System Administrator",
        })
        return {
            "token": admin_jwt,
            "access_token": admin_jwt,
            "token_type": "bearer",
            "role": "admin",
        }
    raise HTTPException(status_code=401, detail="Invalid admin credentials.")


@app.get("/admin/analytics")
async def admin_analytics(
    admin_key: str = "",
    token: str = "",
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Returns aggregated, anonymized analytics for the dashboard charts.
    """
    supplied_token = admin_key or token
    _verify_admin_access(supplied_token, current_user)
    try:
        return get_analytics_summary()
    except Exception as e:
        log.error(f"Analytics error: {e}")
        raise HTTPException(status_code=500, detail="Analytics query failed.")


@app.get("/admin/users")
async def admin_users(
    admin_key: str = "",
    token: str = "",
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Returns anonymized user list for the admin panel.
    """
    supplied_token = admin_key or token
    _verify_admin_access(supplied_token, current_user)
    try:
        return get_all_users_admin()
    except Exception as e:
        log.error(f"Admin users error: {e}")
        raise HTTPException(status_code=500, detail="User query failed.")


@app.post("/admin/users/{user_id}/role")
async def admin_update_role(
    user_id: int,
    body: dict,
    admin_key: str = "",
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Allows the admin to promote or demote a user's role.
    """
    _verify_admin_access(admin_key, current_user)
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


# ===========================================================================
# SERVER RUNNER (Supports Hugging Face Spaces Port 7860 & Cloud Runtimes)
# ===========================================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 7860))
    host = os.getenv("HOST", "0.0.0.0")
    log.info(f"🚀 Starting Health Assistant API on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
