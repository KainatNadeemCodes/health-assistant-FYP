"""
FILE: src/voice_processor.py
PURPOSE: Microphone capture and Speech-to-Text Transcription
VERSION: 1.0  |  GROUP: F25PROJECT664B0

This module handles the voice-to-text pipeline. It captures audio from the 
hardware microphone, calibrates for background noise (TC-06), and uses 
Google's Speech Recognition API to convert symptoms into English or Urdu text.
"""

import logging
import time
from typing import Optional

# ── Logging Configuration ─────────────────────────────────────────────────
log = logging.getLogger(__name__)

# ── Recording Parameters (SRS UC-02 & Prompt Specs) ──────────────────────
# We strictly enforce these windows to ensure clips are manageable.
MIN_RECORD_SECONDS   : int   = 8     # Minimum duration per SRS
MAX_RECORD_SECONDS   : int   = 15    # Maximum duration per SRS
DEFAULT_DURATION     : int   = 10    
CALIBRATION_SECONDS  : float = 1.5   # Time spent "listening" to room noise
RECOGNITION_TIMEOUT  : int   = 5     # Wait time before giving up on speech
PHRASE_TIME_LIMIT    : int   = MAX_RECORD_SECONDS 

# ── Language Support (FR9) ────────────────────────────────────────────────
LANGUAGE_ENGLISH = "en-US"
LANGUAGE_URDU    = "ur-PK"

# ── Quality Control ───────────────────────────────────────────────────────
MIN_TEXT_LENGTH = 5


# ===========================================================================
# CUSTOM EXCEPTIONS
# ===========================================================================
# These allow our FastAPI endpoints to return specific, helpful error 
# messages rather than generic 500 server errors.

class VoiceInputError(Exception):
    """Generic base for all voice-related failures."""

class MicrophoneNotFoundError(VoiceInputError):
    """Raised if the OS can't find a mic or permission is denied."""

class SilentInputError(VoiceInputError):
    """Raised if the recording is just dead air."""

class NoiseError(VoiceInputError):
    """Raised if the environment is too loud to distinguish speech."""

class TranscriptionError(VoiceInputError):
    """Raised if Google receives the audio but can't decode it."""

class NetworkError(VoiceInputError):
    """Raised if the local machine is offline (Google API needs internet)."""

class DurationError(VoiceInputError):
    """Raised if the API request asks for a clip length outside 8-15s."""


# ===========================================================================
# SPEECH ENGINE BOOTSTRAP
# ===========================================================================

def _import_speech_recognition():
    """
    Imports the speech engine only when needed. This prevents the whole 
    backend from failing to start if a user hasn't installed PyAudio yet.
    """
    try:
        import speech_recognition as sr
        return sr
    except ImportError:
        raise ImportError(
            "Missing 'SpeechRecognition' or 'pyaudio'. "
            "Install them using: pip install SpeechRecognition pyaudio"
        )


# ===========================================================================
# MAIN API FUNCTIONS
# ===========================================================================

def capture_voice_symptoms(
    duration: int  = DEFAULT_DURATION,
    language: str  = LANGUAGE_ENGLISH,
    calibrate: bool = True,
) -> str:
    """
    The primary entry point for voice processing. 
    
    It validates the request, handles the hardware handshake, records the 
    user's symptoms, and returns a clean string.
    """
    sr = _import_speech_recognition()

    # 1. Enforce SRS duration constraints immediately
    _validate_duration(duration)

    recognizer = sr.Recognizer()

    # 2. Hardware check
    try:
        mic = sr.Microphone()
    except (OSError, AttributeError) as exc:
        raise MicrophoneNotFoundError(
            "Microphone unavailable. Check hardware connections and permissions."
        ) from exc

    # 3. Audio Processing Pipeline
    with mic as source:
        if calibrate:
            log.info("Calibrating for room noise...")
            try:
                # This helps filter out fans, AC, or street noise (TC-06)
                recognizer.adjust_for_ambient_noise(source, duration=CALIBRATION_SECONDS)
            except Exception as exc:
                log.warning("Noise calibration failed, proceeding with defaults: %s", exc)

        log.info(f"Recording ({language}) for {duration} seconds...")
        audio = _record_audio(recognizer, source, duration)

    # 4. Conversion to Text
    text = _transcribe(recognizer, audio, language)
    
    log.info("Transcription complete.")
    return text


def is_microphone_available() -> bool:
    """
    System check to see if we can actually record. Useful for 
    health-check endpoints in our FastAPI setup.
    """
    try:
        sr = _import_speech_recognition()
        mic = sr.Microphone()
        with mic:
            pass
        return True
    except Exception:
        return False


# ===========================================================================
# PRIVATE UTILITIES
# ===========================================================================

def _validate_duration(duration: int) -> None:
    """Ensures recording length stays within the 8-15s SRS window."""
    if not isinstance(duration, int) or isinstance(duration, bool):
        raise DurationError("Recording duration must be a whole number.")
    
    if not (MIN_RECORD_SECONDS <= duration <= MAX_RECORD_SECONDS):
        raise DurationError(
            f"Invalid duration ({duration}s). Must be between "
            f"{MIN_RECORD_SECONDS} and {MAX_RECORD_SECONDS} seconds."
        )


def _record_audio(recognizer, source, duration: int):
    """Handles the actual interaction with the microphone stream."""
    sr = _import_speech_recognition()
    try:
        # listen() automatically detects when the user starts speaking
        return recognizer.listen(
            source,
            timeout=RECOGNITION_TIMEOUT,
            phrase_time_limit=duration
        )
    except sr.WaitTimeoutError:
        raise SilentInputError("No speech detected. Please try speaking again.")


def _transcribe(recognizer, audio, language: str) -> str:
    """Communicates with the Google Cloud Speech API."""
    sr = _import_speech_recognition()

    try:
        # Send audio to Google
        raw_text: str = recognizer.recognize_google(audio, language=language)

    except sr.UnknownValueError:
        # Audio was received but Google couldn't make sense of it
        raise TranscriptionError(
            "Audio unclear. Please minimize background noise and speak clearly."
        )

    except sr.RequestError as exc:
        # Something went wrong with the API request (usually network)
        raise NetworkError(
            "Transcription service unreachable. Check your internet connection."
        ) from exc

    # Final cleanup: lowercasing and stripping whitespace
    cleaned = raw_text.strip().lower()

    if len(cleaned) < MIN_TEXT_LENGTH:
        raise SilentInputError("Transcription too short to be a valid symptom.")

    return cleaned


def capture_voice_safe(
    duration: int = DEFAULT_DURATION,
    language: str = LANGUAGE_ENGLISH,
) -> dict:
    """
    A 'safe' wrapper for the API. Instead of raising exceptions, 
    it returns a JSON-friendly dictionary. Ideal for FastAPI responses.
    """
    try:
        text = capture_voice_symptoms(duration=duration, language=language)
        return {
            "status": "success",
            "text": text,
            "error": None
        }
    except Exception as exc:
        error_name = type(exc).__name__
        log.warning(f"Voice capture failed: {error_name} - {exc}")
        return {
            "status": "error",
            "text": "",
            "error": str(exc),
            "error_type": error_name
        }

# ===========================================================================
# LOCAL TESTING
# ===========================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    
    print("\nStarting Voice Processor Local Test...")
    if is_microphone_available():
        print("Microphone detected. Speak now (English)...")
        result = capture_voice_safe(duration=8)
        print(f"Result: {result}")
    else:
        print("No microphone found. Check your hardware settings.")