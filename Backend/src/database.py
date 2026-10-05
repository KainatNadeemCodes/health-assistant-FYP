"""
FILE: src/database.py
PURPOSE: SQLite Persistence Layer for Users, Consultations, and Feedback
VERSION: 2.0  |  GROUP: F25PROJECT664B0
SUPERVISOR: Shakeel Saeed

This module is the "Source of Truth" for the entire application. Everything
that needs to be remembered between sessions lives here — user accounts,
consultation history, feedback ratings, and the analytics data the admin
dashboard relies on.

Changes in v2.0:
  - Added get_analytics_summary()  → feeds AdminDashboard charts
  - Added get_all_users_admin()    → feeds AdminDashboard user table
  - Added update_user_role()       → RBAC role management from admin panel
  All three were imported by app.py but missing here — causing ImportError on startup.
"""

import sqlite3
import hashlib
import logging
import json
import os
DB_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "health_assistant.db")
from datetime import datetime
from typing import Optional

# ── Logging ───────────────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
# DB sits in the Backend folder by default, next to app.py
DB_PATH: str = "health_assistant.db"

# SRS FR11 — defined user roles
ROLE_GUEST   = "Guest"
ROLE_PATIENT = "Patient"
VALID_ROLES  = {ROLE_GUEST, ROLE_PATIENT}

VALID_GENDERS = {"Male", "Female", "Other", "Prefer not to say"}


# ===========================================================================
# DATABASE ENGINE
# ===========================================================================

def get_connection(path: str = DB_PATH) -> sqlite3.Connection:
    """
    Opens a thread-safe SQLite connection with WAL mode enabled.
    WAL = Write-Ahead Logging → multiple readers + one writer can work at the
    same time without blocking each other. Essential for FastAPI's async nature.
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # lets us do row["email"] instead of row[0]
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(path: str = DB_PATH) -> None:
    """
    Initializes all tables. Safe to call on every startup because
    we use 'IF NOT EXISTS' — no data gets wiped.

    Tables created:
      users         → accounts and profiles
      consultations → AI prediction history
      feedback      → user ratings per consultation
    """
    parent_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent_dir, exist_ok=True)

    conn = get_connection(path)
    try:
        cur = conn.cursor()

        # --- 1. Users ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    NOT NULL,
                email         TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                age           INTEGER,
                gender        TEXT,
                role          TEXT    NOT NULL DEFAULT 'Patient'
                                      CHECK (role IN ('Guest', 'Patient')),
                created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # --- 2. Consultations ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS consultations (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
                symptoms     TEXT    NOT NULL,
                prediction   TEXT    NOT NULL,
                triage_level TEXT    NOT NULL
                                     CHECK (triage_level IN ('Low','Medium','High')),
                specialist   TEXT    NOT NULL DEFAULT 'General Physician',
                timestamp    TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # --- 3. Feedback ---
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                consult_id INTEGER NOT NULL UNIQUE
                                   REFERENCES consultations(id) ON DELETE CASCADE,
                rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                comments   TEXT,
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Performance indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_consults_user ON consultations(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_consults_time ON consultations(timestamp)")

        conn.commit()
        log.info(f"Database ready at: {path}")
    finally:
        conn.close()


# ===========================================================================
# SECURITY HELPERS
# ===========================================================================

def _hash_password(plain_text: str) -> str:
    """SHA-256 hashing. We never store passwords as plain text — ever."""
    return hashlib.sha256(plain_text.encode("utf-8")).hexdigest()


def _verify_password(plain_text: str, stored_hash: str) -> bool:
    """Constant-time comparison to check login credentials."""
    return _hash_password(plain_text) == stored_hash


# ===========================================================================
# USER MANAGEMENT
# ===========================================================================

def register_user(
    username: str,
    email: str,
    password: str,
    age: int = None,
    gender: str = None,
    role: str = ROLE_PATIENT,
) -> Optional[dict]:
    """
    Creates a new user account.
    Returns the user object on success, or None if the email is already taken.
    """
    if not email or "@" not in email:
        raise ValueError("A valid email address is required.")

    p_hash = _hash_password(password)
    conn   = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, email, password_hash, age, gender, role) VALUES (?,?,?,?,?,?)",
            (username.strip(), email.strip().lower(), p_hash, age, gender, role),
        )
        conn.commit()
        # Return the full user record by doing a fresh login query
        return login_user(email, password)
    except sqlite3.IntegrityError:
        log.warning(f"Registration failed — email already exists: {email}")
        return None
    finally:
        conn.close()


def login_user(email: str, password: str) -> Optional[dict]:
    """
    Authenticates a user. Returns their profile dict (no password hash included)
    or None if credentials are wrong.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),))
        row = cur.fetchone()

        if row and _verify_password(password, row["password_hash"]):
            user_data = dict(row)
            del user_data["password_hash"]  # never send this to the frontend
            return user_data
        return None
    finally:
        conn.close()


# ===========================================================================
# CONSULTATION (MEDICAL HISTORY) MANAGEMENT
# ===========================================================================

def save_consultation(
    symptoms:   str,
    prediction: str,
    triage:     str,
    specialist: str,
    user_id:    Optional[int] = None,
) -> int:
    """
    Saves an AI consultation result to the database.
    Works for both registered users (user_id set) and guests (user_id=None).

    The triage param must be 'Low', 'Medium', or 'High' — the DB CHECK constraint
    enforces this. The /predict endpoint maps frontend values before calling here.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO consultations (user_id, symptoms, prediction, triage_level, specialist)
               VALUES (?, ?, ?, ?, ?)""",
            (user_id, symptoms, prediction, triage, specialist),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def fetch_history(user_id: int, limit: int = 10) -> list:
    """
    Pulls the most recent [limit] consultations for a registered user.
    Called by the Dashboard page when a logged-in user wants to see their history.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM consultations WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit),
        )
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


# ===========================================================================
# FEEDBACK
# ===========================================================================

def save_feedback(consult_id: int, rating: int, comments: str = None) -> Optional[int]:
    """
    UC-08: Saves user feedback (1–5 star rating) for a consultation.
    Returns the new feedback ID, or None if feedback already exists for this consult.
    """
    if not (1 <= rating <= 5):
        raise ValueError("Rating must be between 1 and 5.")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feedback (consult_id, rating, comments) VALUES (?, ?, ?)",
            (consult_id, rating, comments),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        # The UNIQUE constraint on consult_id means one feedback per consultation
        log.warning(f"Duplicate feedback attempt for consult_id={consult_id}")
        return None
    finally:
        conn.close()


# ===========================================================================
# ADMIN FUNCTIONS — These were missing in v1 and caused ImportError on startup
# ===========================================================================

def get_analytics_summary() -> dict:
    """
    Aggregates anonymized stats for the admin analytics dashboard.

    Returns:
      total_consultations  → headline stat card
      total_users          → headline stat card
      avg_rating           → headline stat card (from feedback table)
      total_feedback       → how many users left ratings
      triage_distribution  → {"Low": 12, "Medium": 7, "High": 3} for pie chart
      top_conditions       → [{"prediction": str, "count": int}] for bar chart
      top_specialists      → [{"specialist": str, "count": int}] for bar chart
      daily_activity       → [{"date": str, "count": int}] for 14-day line chart
      recent_consultations → last 10 rows for the "Knowledge Base" review table
                             (symptoms are truncated to 80 chars — no full PII exposure)
    """
    conn = get_connection()
    try:
        cur = conn.cursor()

        # --- Headline metrics ---
        cur.execute("SELECT COUNT(*) FROM consultations")
        total_consultations = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM users")
        total_users = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*), ROUND(AVG(rating), 1) FROM feedback")
        fb_row            = cur.fetchone()
        total_feedback    = fb_row[0] or 0
        avg_rating        = fb_row[1] or 0.0

        # --- Triage distribution for pie chart ---
        cur.execute("""
            SELECT triage_level, COUNT(*) as cnt
            FROM consultations
            GROUP BY triage_level
        """)
        triage_distribution = {row["triage_level"]: row["cnt"] for row in cur.fetchall()}

        # --- Top 10 predicted conditions for bar chart ---
        cur.execute("""
            SELECT prediction, COUNT(*) as cnt
            FROM consultations
            GROUP BY prediction
            ORDER BY cnt DESC
            LIMIT 10
        """)
        top_conditions = [{"prediction": r["prediction"], "count": r["cnt"]} for r in cur.fetchall()]

        # --- Top specialists demanded ---
        cur.execute("""
            SELECT specialist, COUNT(*) as cnt
            FROM consultations
            WHERE specialist IS NOT NULL AND specialist != ''
            GROUP BY specialist
            ORDER BY cnt DESC
            LIMIT 10
        """)
        top_specialists = [{"specialist": r["specialist"], "count": r["cnt"]} for r in cur.fetchall()]

        # --- Daily activity: last 14 days ---
        cur.execute("""
            SELECT DATE(timestamp) as date, COUNT(*) as cnt
            FROM consultations
            WHERE DATE(timestamp) >= DATE('now', '-14 days')
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        """)
        daily_activity = [{"date": r["date"], "count": r["cnt"]} for r in cur.fetchall()]

        # --- Recent consultations for knowledge base review ---
        # Symptoms are truncated to avoid exposing full patient input in the dashboard
        cur.execute("""
            SELECT c.id, c.prediction, c.triage_level, c.specialist,
                   c.timestamp,
                   SUBSTR(c.symptoms, 1, 80) as symptoms_preview
            FROM consultations c
            ORDER BY c.timestamp DESC
            LIMIT 10
        """)
        recent_consultations = [dict(row) for row in cur.fetchall()]

        return {
            "total_consultations":  total_consultations,
            "total_users":          total_users,
            "avg_rating":           avg_rating,
            "total_feedback":       total_feedback,
            "triage_distribution":  triage_distribution,
            "top_conditions":       top_conditions,
            "top_specialists":      top_specialists,
            "daily_activity":       daily_activity,
            "recent_consultations": recent_consultations,
        }

    except Exception as e:
        log.error(f"get_analytics_summary failed: {e}")
        # Return empty structure instead of crashing the admin dashboard
        return {
            "total_consultations":  0,
            "total_users":          0,
            "avg_rating":           0.0,
            "total_feedback":       0,
            "triage_distribution":  {},
            "top_conditions":       [],
            "top_specialists":      [],
            "daily_activity":       [],
            "recent_consultations": [],
        }
    finally:
        conn.close()


def get_all_users_admin() -> list:
    """
    Returns anonymized user list for the admin panel user table.
    Password hashes are stripped. Sensitive health data is NOT included.
    Only basic account metadata and consultation count are returned.
    This satisfies SRS NFR-4 (Security) — admin can see users but not their medical records.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                u.id,
                u.username,
                u.email,
                u.role,
                u.age,
                u.gender,
                u.created_at,
                COUNT(c.id) as consultation_count
            FROM users u
            LEFT JOIN consultations c ON c.user_id = u.id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def update_user_role(user_id: int, new_role: str) -> bool:
    """
    RBAC: Allows admin to change a user's role (Guest ↔ Patient).
    Returns True if the user was found and updated, False if user_id doesn't exist.
    Called by POST /admin/users/{user_id}/role in app.py.
    """
    if new_role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{new_role}'. Must be one of: {VALID_ROLES}")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            (new_role, user_id),
        )
        conn.commit()
        # rowcount tells us if the UPDATE actually matched anything
        return cur.rowcount > 0
    finally:
        conn.close()


# ===========================================================================
# QUICK SELF-TEST
# ===========================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db("test_health.db")
    print("Self-test: DB initialized OK.")
    summary = get_analytics_summary()
    print(f"Analytics OK — {summary['total_consultations']} consultations in test DB.")
    if os.path.exists("test_health.db"):
        os.remove("test_health.db")
    print("Cleanup done. All good.")