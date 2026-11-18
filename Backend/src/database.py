"""
FILE: src/database.py
PURPOSE: Enterprise Dual-Engine Persistence Layer (SQLite & PostgreSQL) via SQLAlchemy 2.0
VERSION: 3.0  |  GROUP: F25PROJECT664B0
SUPERVISOR: Shakeel Saeed

This module provides a robust, decoupled data persistence layer supporting both:
  1. Local zero-config development (SQLite with WAL mode and PRAGMA foreign keys)
  2. Production deployment (PostgreSQL / AWS RDS / GCP Cloud SQL via DATABASE_URL)

Architecture:
  - Declarative SQLAlchemy 2.0 ORM models with strong type annotations.
  - Connection pooling with pre-ping validation (`pool_pre_ping=True`).
  - Thread-safe session management via context-managed sessions.
  - Full backward compatibility for all existing service and test callers.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from sqlalchemy import (
    create_engine,
    select,
    func,
    desc,
    event,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    CheckConstraint,
    Engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
    Session,
)
from sqlalchemy.exc import IntegrityError

try:
    from src.security import (
        hash_password as secure_hash_password,
        verify_password as secure_verify_password,
    )
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from src.security import (
        hash_password as secure_hash_password,
        verify_password as secure_verify_password,
    )

# ── Logging ───────────────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

# ── Load Environment Variables (Neon .env.local and .env support) ─────────────
try:
    from dotenv import load_dotenv
    _backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _root_dir = os.path.dirname(_backend_dir)
    for _env_file in [
        os.path.join(_root_dir, ".env.local"),
        os.path.join(_root_dir, ".env"),
        os.path.join(_backend_dir, ".env.local"),
        os.path.join(_backend_dir, ".env"),
    ]:
        if os.path.exists(_env_file):
            load_dotenv(_env_file, override=False)
except ImportError:
    pass

# ── Config & URL Resolution ───────────────────────────────────────────────────
DEFAULT_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "health_assistant.db")

# Defined user roles
ROLE_GUEST   = "Guest"
ROLE_PATIENT = "Patient"
ROLE_ADMIN   = "Admin"
VALID_ROLES  = {ROLE_GUEST, ROLE_PATIENT, ROLE_ADMIN}
VALID_GENDERS = {"Male", "Female", "Other", "Prefer not to say"}


def resolve_database_url(custom_target: Optional[str] = None) -> str:
    """
    Resolves the active database connection string.
    Priority:
      1. Explicit function argument (file path or URI)
      2. Environment variable DATABASE_URL (production)
      3. Environment variable DATABASE_PATH (custom SQLite path)
      4. Default local SQLite file path
    """
    target = custom_target or os.getenv("DATABASE_URL")
    if target:
        # Standard cloud compatibility: rewrite legacy postgres:// to postgresql://
        if target.startswith("postgres://"):
            target = target.replace("postgres://", "postgresql://", 1)
        # Automatic driver resolution: fallback to psycopg2 if psycopg (v3) is not installed
        if target.startswith("postgresql://"):
            try:
                import psycopg  # noqa: F401
            except ImportError:
                try:
                    import psycopg2  # noqa: F401
                    target = target.replace("postgresql://", "postgresql+psycopg2://", 1)
                except ImportError:
                    pass
        if "://" in target:
            return target
        # If it's a file path provided in target
        return f"sqlite:///{os.path.abspath(target)}"

    sqlite_path = os.getenv("DATABASE_PATH", DEFAULT_DB_FILE)
    return f"sqlite:///{os.path.abspath(sqlite_path)}"


# Global Engine and Session Factory State
_ENGINE: Optional[Engine] = None
_SESSION_FACTORY: Optional[sessionmaker] = None


def close_engine():
    """Closes and disposes of the connection pool, releasing file locks."""
    global _ENGINE, _SESSION_FACTORY
    if _ENGINE is not None:
        _ENGINE.dispose()
        _ENGINE = None
        _SESSION_FACTORY = None


def get_engine(db_url: Optional[str] = None) -> Engine:
    """
    Returns or lazily initializes the singleton SQLAlchemy Engine.
    Configures SQLite with WAL mode and foreign key enforcement.
    """
    global _ENGINE, _SESSION_FACTORY
    target_url = resolve_database_url(db_url)

    # Recreate engine if URL changes (e.g. during test suite isolation)
    if _ENGINE is not None:
        current_url = str(_ENGINE.url)
        if current_url == target_url:
            return _ENGINE

    is_sqlite = target_url.startswith("sqlite")
    engine_kwargs: Dict[str, Any] = {
        "pool_pre_ping": True,
    }

    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    _ENGINE = create_engine(target_url, **engine_kwargs)

    # Enable WAL mode and Foreign Keys for SQLite
    if is_sqlite:
        @event.listens_for(_ENGINE, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys = ON")
                cursor.execute("PRAGMA journal_mode = WAL")
            except Exception as e:
                log.debug(f"SQLite PRAGMA setup note: {e}")
            finally:
                cursor.close()

    _SESSION_FACTORY = sessionmaker(autocommit=False, autoflush=False, bind=_ENGINE)
    return _ENGINE


def get_session_factory() -> sessionmaker:
    """Returns the current sessionmaker, ensuring the engine is initialized."""
    global _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        get_engine()
    return _SESSION_FACTORY


@contextmanager
def get_db():
    """Context manager for thread-safe database sessions with automatic rollback."""
    session_cls = get_session_factory()
    session: Session = session_cls()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_connection(path: Optional[str] = None):
    """
    Backward-compatible connection accessor for legacy callers.
    Returns a raw DBAPI connection.
    """
    eng = get_engine(path)
    return eng.raw_connection()


# ===========================================================================
# DECLARATIVE ORM MODELS
# ===========================================================================

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative tables."""
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_PATIENT)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("role IN ('Guest', 'Patient', 'Admin')", name="ck_users_role"),
    )

    consultations = relationship("Consultation", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "age": self.age,
            "gender": self.gender,
            "role": self.role,
            "created_at": self.created_at.isoformat() if hasattr(self.created_at, "isoformat") else str(self.created_at),
        }


class Consultation(Base):
    __tablename__ = "consultations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    symptoms: Mapped[str] = mapped_column(Text, nullable=False)
    prediction: Mapped[str] = mapped_column(String(100), nullable=False)
    triage_level: Mapped[str] = mapped_column(String(20), nullable=False)
    specialist: Mapped[str] = mapped_column(String(100), nullable=False, default="General Physician")
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        CheckConstraint("triage_level IN ('Low', 'Medium', 'High')", name="ck_consult_triage"),
    )

    user = relationship("User", back_populates="consultations")
    feedback = relationship("Feedback", back_populates="consultation", uselist=False, cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "symptoms": self.symptoms,
            "prediction": self.prediction,
            "triage_level": self.triage_level,
            "specialist": self.specialist,
            "timestamp": self.timestamp.isoformat() if hasattr(self.timestamp, "isoformat") else str(self.timestamp),
        }


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    consult_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("consultations.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedback_rating"),
    )

    consultation = relationship("Consultation", back_populates="feedback")


# ===========================================================================
# DATABASE INITIALIZATION
# ===========================================================================

def init_db(path: Optional[str] = None) -> None:
    """
    Initializes all database tables. Safe to call on application startup.
    Supports both SQLite file paths and PostgreSQL connection strings.
    """
    eng = get_engine(path)
    # Ensure directory exists for local SQLite files
    if str(eng.url).startswith("sqlite"):
        db_path = eng.url.database
        if db_path and db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    Base.metadata.create_all(bind=eng)
    log.info(f"Database schema initialized successfully on: {eng.url.render_as_string(hide_password=True)}")


# ===========================================================================
# SECURITY HELPERS
# ===========================================================================

def _hash_password(plain_text: str) -> str:
    """Salted PBKDF2-HMAC-SHA256 hashing via security module."""
    return secure_hash_password(plain_text)


def _verify_password(plain_text: str, stored_hash: str) -> bool:
    """Verifies password using PBKDF2 with automatic fallback for legacy SHA-256."""
    return secure_verify_password(plain_text, stored_hash)


# ===========================================================================
# USER MANAGEMENT
# ===========================================================================

def register_user(
    username: str,
    email: str,
    password: str,
    age: Optional[int] = None,
    gender: Optional[str] = None,
    role: str = ROLE_PATIENT,
) -> Optional[dict]:
    """
    Creates a new user account.
    Returns the user profile on success, or None if the email is already registered.
    """
    if not email or "@" not in email:
        raise ValueError("A valid email address is required.")

    p_hash = _hash_password(password)
    clean_email = email.strip().lower()

    try:
        with get_db() as session:
            new_user = User(
                username=username.strip(),
                email=clean_email,
                password_hash=p_hash,
                age=age,
                gender=gender,
                role=role,
            )
            session.add(new_user)
            session.flush()
    except IntegrityError:
        log.warning(f"Registration failed — email already exists: {clean_email}")
        return None

    return login_user(clean_email, password)


def login_user(email: str, password: str) -> Optional[dict]:
    """
    Authenticates a user. Returns their profile dict (password hash omitted)
    or None if credentials are invalid.
    Automatically upgrades legacy SHA-256 hashes to salted PBKDF2 upon success.
    """
    clean_email = email.strip().lower()

    with get_db() as session:
        user = session.execute(
            select(User).where(User.email == clean_email)
        ).scalar_one_or_none()

        if user and _verify_password(password, user.password_hash):
            if not user.password_hash.startswith("pbkdf2_"):
                user.password_hash = _hash_password(password)
                session.flush()

            user_data = user.to_dict()
            return user_data

    return None


# ===========================================================================
# CONSULTATION (MEDICAL HISTORY) MANAGEMENT
# ===========================================================================

def save_consultation(
    symptoms: str,
    prediction: str,
    triage: str,
    specialist: str,
    user_id: Optional[int] = None,
) -> int:
    """
    Saves an AI consultation result to the database.
    Works for registered users and guests (user_id=None).
    """
    with get_db() as session:
        consultation = Consultation(
            user_id=user_id,
            symptoms=symptoms,
            prediction=prediction,
            triage_level=triage,
            specialist=specialist,
        )
        session.add(consultation)
        session.flush()
        return consultation.id


def fetch_history(user_id: int, limit: int = 10) -> List[dict]:
    """
    Pulls the most recent [limit] consultations for a registered user.
    """
    with get_db() as session:
        results = session.execute(
            select(Consultation)
            .where(Consultation.user_id == user_id)
            .order_by(desc(Consultation.timestamp))
            .limit(limit)
        ).scalars().all()

        return [c.to_dict() for c in results]


# ===========================================================================
# FEEDBACK
# ===========================================================================

def save_feedback(consult_id: int, rating: int, comments: Optional[str] = None) -> Optional[int]:
    """
    Saves user feedback (1–5 star rating) for a consultation.
    Returns the new feedback ID, or None if feedback already exists for this consult.
    """
    if not (1 <= rating <= 5):
        raise ValueError("Rating must be between 1 and 5.")

    try:
        with get_db() as session:
            feedback = Feedback(
                consult_id=consult_id,
                rating=rating,
                comments=comments,
            )
            session.add(feedback)
            session.flush()
            return feedback.id
    except IntegrityError:
        log.warning(f"Duplicate feedback attempt for consult_id={consult_id}")
        return None


# ===========================================================================
# ADMIN FUNCTIONS
# ===========================================================================

def get_analytics_summary() -> dict:
    """
    Aggregates anonymized stats for the admin analytics dashboard.
    Compatible across SQLite and PostgreSQL.
    """
    try:
        with get_db() as session:
            total_consultations = session.execute(
                select(func.count(Consultation.id))
            ).scalar_one() or 0

            total_users = session.execute(
                select(func.count(User.id))
            ).scalar_one() or 0

            fb_stats = session.execute(
                select(func.count(Feedback.id), func.avg(Feedback.rating))
            ).one()
            total_feedback = fb_stats[0] or 0
            avg_rating = round(float(fb_stats[1]), 1) if fb_stats[1] is not None else 0.0

            # Triage distribution
            triage_rows = session.execute(
                select(Consultation.triage_level, func.count(Consultation.id))
                .group_by(Consultation.triage_level)
            ).all()
            triage_distribution = {row[0]: row[1] for row in triage_rows}

            # Top 10 predicted conditions
            top_cond_rows = session.execute(
                select(Consultation.prediction, func.count(Consultation.id).label("cnt"))
                .group_by(Consultation.prediction)
                .order_by(desc("cnt"))
                .limit(10)
            ).all()
            top_conditions = [{"prediction": r[0], "count": r[1]} for r in top_cond_rows]

            # Top specialists
            top_spec_rows = session.execute(
                select(Consultation.specialist, func.count(Consultation.id).label("cnt"))
                .where(Consultation.specialist.isnot(None), Consultation.specialist != "")
                .group_by(Consultation.specialist)
                .order_by(desc("cnt"))
                .limit(10)
            ).all()
            top_specialists = [{"specialist": r[0], "count": r[1]} for r in top_spec_rows]

            # Daily activity (last 14 days)
            # func.cast or func.date works cross-dialect
            date_col = func.date(Consultation.timestamp)
            daily_rows = session.execute(
                select(date_col.label("day"), func.count(Consultation.id).label("cnt"))
                .group_by("day")
                .order_by("day")
                .limit(14)
            ).all()
            daily_activity = [{"date": str(r[0]), "count": r[1]} for r in daily_rows]

            # Recent consultations
            recent_rows = session.execute(
                select(Consultation)
                .order_by(desc(Consultation.timestamp))
                .limit(10)
            ).scalars().all()

            recent_consultations = [
                {
                    "id": c.id,
                    "prediction": c.prediction,
                    "triage_level": c.triage_level,
                    "specialist": c.specialist,
                    "timestamp": c.timestamp.isoformat() if hasattr(c.timestamp, "isoformat") else str(c.timestamp),
                    "symptoms_preview": c.symptoms[:80] if c.symptoms else "",
                }
                for c in recent_rows
            ]

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


def get_all_users_admin() -> List[dict]:
    """
    Returns sanitized user list with consultation counts for the admin dashboard.
    """
    with get_db() as session:
        rows = session.execute(
            select(
                User.id,
                User.username,
                User.email,
                User.role,
                User.age,
                User.gender,
                User.created_at,
                func.count(Consultation.id).label("consultation_count"),
            )
            .outerjoin(Consultation, Consultation.user_id == User.id)
            .group_by(User.id)
            .order_by(desc(User.created_at))
        ).all()

        return [
            {
                "id": r[0],
                "username": r[1],
                "email": r[2],
                "role": r[3],
                "age": r[4],
                "gender": r[5],
                "created_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
                "consultation_count": r[7],
            }
            for r in rows
        ]


def update_user_role(user_id: int, new_role: str) -> bool:
    """
    Allows admin to update a user's role.
    """
    if new_role not in VALID_ROLES:
        raise ValueError(f"Invalid role '{new_role}'. Must be one of: {VALID_ROLES}")

    with get_db() as session:
        user = session.execute(
            select(User).where(User.id == user_id)
        ).scalar_one_or_none()

        if not user:
            return False

        user.role = new_role
        session.flush()
        return True


# ===========================================================================
# QUICK SELF-TEST
# ===========================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_db = "test_health_phase4.db"
    if os.path.exists(test_db):
        os.remove(test_db)

    init_db(test_db)
    print("Self-test: DB initialized OK via SQLAlchemy.")

    user = register_user("Test Doctor", "doctor@test.com", "SecurePass123!", role=ROLE_PATIENT)
    print("Registered:", user)

    login_res = login_user("doctor@test.com", "SecurePass123!")
    print("Logged in:", login_res)

    cid = save_consultation("fever, cough", "Flu", "Medium", "General Physician", user["id"])
    print("Saved consultation ID:", cid)

    fid = save_feedback(cid, 5, "Accurate triage!")
    print("Saved feedback ID:", fid)

    summary = get_analytics_summary()
    print("Analytics summary:", summary)

    users_admin = get_all_users_admin()
    print("Admin users:", users_admin)

    updated = update_user_role(user["id"], ROLE_ADMIN)
    print("Role updated:", updated)

    close_engine()
    if os.path.exists(test_db):
        os.remove(test_db)
    print("Cleanup done. All phase 4 database tests passed!")
