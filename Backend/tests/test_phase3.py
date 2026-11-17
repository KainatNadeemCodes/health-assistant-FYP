"""
Unit and Integration Tests for Phase 3: Clinical Negation & Out-of-Vocabulary Safety Guardrails
"""

import os
import sys
import unittest
from fastapi.testclient import TestClient

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

os.environ["DATABASE_PATH"] = os.path.join(backend_dir, "test_guardrails_health_assistant.db")
os.environ["ADMIN_SECRET"] = "guardrailtestadmin2025"

from app import app
from src.clinical_guardrails import (
    is_phrase_negated,
    filter_affirmed_keywords,
    evaluate_prediction_confidence,
)
from src.triage import generate_triage
from src.feature_extraction import load_vectorizer, transform_text
from src.preprocessing import clean_text
from src.database import init_db


class TestPhase3ClinicalGuardrails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_db = os.environ.get("DATABASE_PATH")
        if test_db and os.path.exists(test_db):
            try:
                os.remove(test_db)
            except OSError:
                pass
        init_db()
        cls.client = TestClient(app)
        cls.vectorizer = load_vectorizer()

    @classmethod
    def tearDownClass(cls):
        test_db = os.environ.get("DATABASE_PATH")
        if test_db and os.path.exists(test_db):
            try:
                os.remove(test_db)
            except OSError:
                pass

    def test_01_english_clinical_negation(self):
        # Direct negation
        self.assertTrue(is_phrase_negated("chest pain", "patient has no chest pain"))
        self.assertTrue(is_phrase_negated("shortness of breath", "denies shortness of breath"))
        self.assertTrue(is_phrase_negated("fever", "without any fever or chills"))
        self.assertTrue(is_phrase_negated("headache", "never had any headache"))

        # Contrastive clauses (headache affirmed, vomiting negated)
        text = "I have a severe throbbing headache, but no vomiting and no neck stiffness."
        self.assertFalse(is_phrase_negated("headache", text))
        self.assertTrue(is_phrase_negated("vomiting", text))
        self.assertTrue(is_phrase_negated("neck stiffness", text))

        affirmed = filter_affirmed_keywords(["headache", "vomiting", "neck stiffness"], text)
        self.assertEqual(affirmed, ["headache"])

    def test_02_urdu_clinical_negation(self):
        # Urdu post-negation
        self.assertTrue(is_phrase_negated("سینے میں درد", "مریض کو سینے میں درد نہیں ہے"))
        self.assertTrue(is_phrase_negated("سانس پھولنا", "سانس پھولنے کی تکلیف نہیں ہو رہی"))

        # Urdu contrastive clause (cough affirmed, chest pain negated)
        ur_text = "ہلکی کھانسی اور نزلہ ہے لیکن سینے میں کوئی درد نہیں ہے"
        self.assertFalse(is_phrase_negated("کھانسی", ur_text))
        self.assertTrue(is_phrase_negated("سینے میں درد", ur_text))

        affirmed_ur = filter_affirmed_keywords(["کھانسی", "سینے میں درد"], ur_text)
        self.assertEqual(affirmed_ur, ["کھانسی"])

    def test_03_false_emergency_triage_prevention(self):
        # Case 1: Runny nose with negated chest pain
        # Without negation handling, "chest pain" would falsely escalate Common Cold to High (Urgent Care).
        symptoms_negated = "runny nose and sneezing, but no chest pain and no difficulty breathing"
        cleaned = clean_text(symptoms_negated)
        triage = generate_triage("Common Cold", 0.85, cleaned)
        # Should stay at Common Cold baseline (Low), NOT escalate to High!
        self.assertEqual(triage["triage_level"], "Low")

        # Case 2: Affirmed chest pain MUST trigger High (Urgent Care)
        symptoms_affirmed = "runny nose along with severe chest pain and breathlessness"
        cleaned_aff = clean_text(symptoms_affirmed)
        triage_aff = generate_triage("Common Cold", 0.60, cleaned_aff)
        self.assertEqual(triage_aff["triage_level"], "High")

    def test_04_oov_gibberish_handling_in_predict(self):
        # Completely non-medical / OOV input
        res = self.client.post("/predict", json={
            "symptoms": "the blue computer laptop is swimming in the sky with a pencil"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        # Must NOT hallucinate a medical diagnosis!
        self.assertIn("error", data)
        self.assertEqual(len(data["conditions"]), 0)

    def test_05_predict_with_negated_symptoms_integration(self):
        # Integration test for /predict with negated red flag
        res = self.client.post("/predict", json={
            "symptoms": "runny nose watery eyes and sneezing, definitely no chest pain and no breathing trouble"
        })
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("conditions", data)
        self.assertGreaterEqual(len(data["conditions"]), 1)
        # Triage must be self-care or visit-gp, definitely NOT urgent-care!
        self.assertNotEqual(data["triage_level"], "urgent-care")
        self.assertEqual(data["triage_level"], "self-care")


if __name__ == "__main__":
    unittest.main()
