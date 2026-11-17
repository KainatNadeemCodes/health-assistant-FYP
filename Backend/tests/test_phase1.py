"""
Unit and Integration Tests for Phase 1: Bugfixes, Security Hardening & IDOR Protection
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure Backend directory is in path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Use an isolated test database
os.environ["DATABASE_PATH"] = os.path.join(backend_dir, "test_health_assistant.db")
os.environ["ADMIN_SECRET"] = "testadminsecret2025"

from app import app
from src.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    ADMIN_SECRET,
)
from src.database import init_db, close_engine


class TestPhase1SecurityAndAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_db = os.environ.get("DATABASE_PATH")
        if test_db and os.path.exists(test_db):
            try:
                os.remove(test_db)
            except OSError:
                pass
        # Initialize fresh test db
        init_db()
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        close_engine()
        test_db = os.environ.get("DATABASE_PATH")
        if test_db and os.path.exists(test_db):
            try:
                os.remove(test_db)
            except OSError:
                pass

    def test_01_password_hashing(self):
        password = "SecurePassword123!"
        hashed = hash_password(password)
        self.assertTrue(hashed.startswith("pbkdf2_sha256$"))
        self.assertTrue(verify_password(password, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

    def test_02_legacy_password_verification(self):
        # Legacy unsalted SHA-256 hash of 'legacy123'
        import hashlib
        legacy_hash = hashlib.sha256("legacy123".encode("utf-8")).hexdigest()
        self.assertTrue(verify_password("legacy123", legacy_hash))
        self.assertFalse(verify_password("wrong", legacy_hash))

    def test_03_jwt_token_flow(self):
        payload = {"sub": "42", "email": "test@example.com", "role": "Patient"}
        token = create_access_token(payload)
        decoded = decode_access_token(token)
        self.assertEqual(decoded["sub"], "42")
        self.assertEqual(decoded["email"], "test@example.com")
        self.assertEqual(decoded["role"], "Patient")

    def test_04_auth_register_and_login(self):
        # Register new user
        reg_payload = {
            "email": "sarah@example.com",
            "password": "Password789!",
            "full_name": "Sarah Connor",
        }
        res_reg = self.client.post("/auth/register", json=reg_payload)
        self.assertEqual(res_reg.status_code, 200, res_reg.text)
        data = res_reg.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["username"], "Sarah Connor")

        # Login
        res_login = self.client.post("/auth/login", json={
            "email": "sarah@example.com",
            "password": "Password789!",
        })
        self.assertEqual(res_login.status_code, 200, res_login.text)
        login_data = res_login.json()
        self.assertIn("access_token", login_data)

    def test_05_history_idor_protection(self):
        # Unauthenticated request to /history must fail with 401
        res = self.client.get("/history")
        self.assertEqual(res.status_code, 401)

        # Authenticate patient 1
        res_reg1 = self.client.post("/auth/register", json={
            "email": "patient1@example.com",
            "password": "Password123!",
            "full_name": "Patient One",
        })
        token1 = res_reg1.json()["access_token"]
        id1 = str(res_reg1.json()["id"])

        # Authenticate patient 2
        res_reg2 = self.client.post("/auth/register", json={
            "email": "patient2@example.com",
            "password": "Password123!",
            "full_name": "Patient Two",
        })
        token2 = res_reg2.json()["access_token"]
        id2 = str(res_reg2.json()["id"])

        # Patient 1 submits symptoms
        self.client.post(
            "/predict",
            json={"symptoms": "fever and dry cough"},
            headers={"Authorization": f"Bearer {token1}"},
        )

        # Patient 2 tries to access Patient 1's history by passing Patient 1's ID
        # The backend must ignore the spoofed user_id and return Patient 2's empty history
        res_idor = self.client.get(
            f"/history?user_id={id1}",
            headers={"Authorization": f"Bearer {token2}"},
        )
        self.assertEqual(res_idor.status_code, 200)
        history = res_idor.json()
        # History for Patient 2 must be empty
        self.assertEqual(len(history), 0)

        # Patient 1 fetches history
        res_p1 = self.client.get("/history", headers={"Authorization": f"Bearer {token1}"})
        self.assertEqual(res_p1.status_code, 200)
        p1_history = res_p1.json()
        self.assertGreaterEqual(len(p1_history), 1)

    def test_06_admin_access_control(self):
        # Patient token should be rejected from admin analytics
        res_patient = self.client.post("/auth/login", json={
            "email": "patient1@example.com",
            "password": "Password123!",
        })
        patient_token = res_patient.json()["access_token"]

        res_unauth = self.client.get(
            "/admin/analytics",
            headers={"Authorization": f"Bearer {patient_token}"},
        )
        self.assertEqual(res_unauth.status_code, 403)

        # Admin login
        res_admin_login = self.client.post("/admin/login", json={"password": ADMIN_SECRET})
        self.assertEqual(res_admin_login.status_code, 200)
        admin_token = res_admin_login.json()["access_token"]

        # Admin can access analytics
        res_admin = self.client.get(
            "/admin/analytics",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        self.assertEqual(res_admin.status_code, 200)
        analytics_data = res_admin.json()
        self.assertIn("total_consultations", analytics_data)


if __name__ == "__main__":
    unittest.main()
