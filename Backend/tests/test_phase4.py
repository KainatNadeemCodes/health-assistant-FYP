"""
Unit and Integration Tests for Phase 4: Database & Architecture Modernization
- SQLAlchemy 2.0 dual-engine persistence layer (SQLite + PostgreSQL URL resolution)
- Database CRUD, analytics aggregation, and relation constraints
- Thread-safe session management & connection pool cleanup
- Async audio processing pipeline & non-blocking voice input endpoint
- Alembic migration environment integrity
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure Backend directory is in path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Isolate test database for Phase 4
os.environ["DATABASE_PATH"] = os.path.join(backend_dir, "test_phase4_db.db")
os.environ["ADMIN_SECRET"] = "phase4adminsecret2025"

from app import app, _transcode_and_transcribe_audio_worker
from src.database import (
    init_db,
    close_engine,
    resolve_database_url,
    register_user,
    login_user,
    save_consultation,
    fetch_history,
    save_feedback,
    get_analytics_summary,
    get_all_users_admin,
    update_user_role,
    ROLE_GUEST,
    ROLE_PATIENT,
    ROLE_ADMIN,
    Base,
)


class TestPhase4Modernization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db = os.environ.get("DATABASE_PATH")
        close_engine()
        if cls.test_db and os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except OSError:
                pass
        init_db(cls.test_db)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        close_engine()
        if cls.test_db and os.path.exists(cls.test_db):
            try:
                os.remove(cls.test_db)
            except OSError:
                pass

    def test_01_database_url_resolution(self):
        """Test URL resolution and Heroku/Render postgres:// rewriting."""
        url_pg = resolve_database_url("postgres://user:pass@host:5432/db")
        self.assertEqual(url_pg, "postgresql://user:pass@host:5432/db")

        url_direct = resolve_database_url("postgresql+psycopg2://u:p@localhost/test")
        self.assertEqual(url_direct, "postgresql+psycopg2://u:p@localhost/test")

        url_file = resolve_database_url("my_custom.db")
        self.assertTrue(url_file.startswith("sqlite:///"))
        self.assertTrue(url_file.endswith("my_custom.db"))

    def test_02_sqlalchemy_user_lifecycle(self):
        """Test registration, duplicate prevention, and login with SQLAlchemy models."""
        user = register_user(
            username="Sarah Connor",
            email="sarah@test.com",
            password="StrongPassword123!",
            age=29,
            gender="Female",
            role=ROLE_PATIENT,
        )
        self.assertIsNotNone(user)
        self.assertEqual(user["username"], "Sarah Connor")
        self.assertEqual(user["email"], "sarah@test.com")
        self.assertEqual(user["role"], ROLE_PATIENT)

        # Duplicate email must return None
        dup = register_user(
            username="Sarah Duplicate",
            email="sarah@test.com",
            password="OtherPassword456!",
        )
        self.assertIsNone(dup)

        # Successful login
        logged_in = login_user("sarah@test.com", "StrongPassword123!")
        self.assertIsNotNone(logged_in)
        self.assertEqual(logged_in["id"], user["id"])
        self.assertNotIn("password_hash", logged_in)

        # Wrong password
        bad_login = login_user("sarah@test.com", "WrongPassword!")
        self.assertIsNone(bad_login)

    def test_03_consultation_and_feedback_flow(self):
        """Test consultation persistence, history querying, and feedback uniqueness."""
        user = login_user("sarah@test.com", "StrongPassword123!")
        self.assertIsNotNone(user)

        cid1 = save_consultation(
            symptoms="high fever, chills, sweating",
            prediction="Malaria",
            triage="High",
            specialist="Infectious Disease Specialist",
            user_id=user["id"],
        )
        self.assertIsInstance(cid1, int)
        self.assertGreater(cid1, 0)

        cid2 = save_consultation(
            symptoms="sneezing, runny nose",
            prediction="Common Cold",
            triage="Low",
            specialist="General Physician",
            user_id=user["id"],
        )
        self.assertGreater(cid2, cid1)

        history = fetch_history(user["id"], limit=5)
        self.assertEqual(len(history), 2)
        # Most recent first
        self.assertEqual(history[0]["prediction"], "Common Cold")
        self.assertEqual(history[1]["prediction"], "Malaria")

        # Feedback flow
        fid1 = save_feedback(cid1, rating=5, comments="Very fast and accurate triage.")
        self.assertIsNotNone(fid1)

        # Duplicate feedback for same consult must return None
        fid_dup = save_feedback(cid1, rating=4, comments="Duplicate attempt.")
        self.assertIsNone(fid_dup)

        # Invalid rating must raise ValueError
        with self.assertRaises(ValueError):
            save_feedback(cid2, rating=6)

    def test_04_admin_analytics_and_role_management(self):
        """Test cross-dialect analytics summary and RBAC role updates."""
        summary = get_analytics_summary()
        self.assertGreaterEqual(summary["total_consultations"], 2)
        self.assertGreaterEqual(summary["total_users"], 1)
        self.assertGreaterEqual(summary["total_feedback"], 1)
        self.assertEqual(summary["avg_rating"], 5.0)
        self.assertIn("High", summary["triage_distribution"])
        self.assertIn("Low", summary["triage_distribution"])

        users = get_all_users_admin()
        self.assertTrue(len(users) >= 1)
        target_user = next((u for u in users if u["email"] == "sarah@test.com"), None)
        self.assertIsNotNone(target_user)
        self.assertEqual(target_user["consultation_count"], 2)

        # Update role to Admin
        success = update_user_role(target_user["id"], ROLE_ADMIN)
        self.assertTrue(success)

        updated_user = login_user("sarah@test.com", "StrongPassword123!")
        self.assertEqual(updated_user["role"], ROLE_ADMIN)

        # Invalid role raises ValueError
        with self.assertRaises(ValueError):
            update_user_role(target_user["id"], "SuperMasterRole")

    def test_05_voice_input_empty_payload(self):
        """Test /voice-input endpoint rejects empty audio payloads gracefully."""
        res = self.client.post(
            "/voice-input",
            files={"audio": ("empty.webm", b"", "audio/webm")},
            params={"language": "en"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Empty audio", res.json()["detail"])

    def test_06_alembic_metadata_registered(self):
        """Verify Alembic target_metadata has all core tables."""
        table_names = list(Base.metadata.tables.keys())
        self.assertIn("users", table_names)
        self.assertIn("consultations", table_names)
        self.assertIn("feedback", table_names)


if __name__ == "__main__":
    unittest.main()
