"""
Unit and Integration Tests for Phase 2: Verified Clinical Dataset Expansion & Prediction Quality
"""

import os
import sys
import unittest
import pandas as pd

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from src.classifier import load_model, predict_top_k
from src.feature_extraction import load_vectorizer, transform_text
from src.preprocessing import clean_text
from src.triage import generate_triage


class TestPhase2ClinicalExpansion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset_path = os.path.join(backend_dir, "data", "dataset.csv")
        cls.model = load_model()
        cls.vectorizer = load_vectorizer()

    def test_01_dataset_integrity_and_volume(self):
        self.assertTrue(os.path.exists(self.dataset_path))
        df = pd.read_csv(self.dataset_path)
        self.assertGreaterEqual(len(df), 3500, "Dataset should have at least 3,500 rows.")
        self.assertEqual(df["disease"].nunique(), 31, "Must contain all 31 disease classes.")

        # Class balance check
        counts = df["disease"].value_counts()
        self.assertGreaterEqual(counts.min(), 100, "Every class must have at least 100 samples.")

        # Null check
        self.assertEqual(df["symptoms"].isnull().sum(), 0)
        self.assertEqual((df["symptoms"].str.strip() == "").sum(), 0)

    def test_02_vectorizer_vocabulary_size(self):
        vocab_size = len(self.vectorizer.vocabulary_)
        self.assertGreaterEqual(vocab_size, 3000, "Vocabulary size should be >= 3000 features.")

    def test_03_english_clinical_predictions(self):
        cases = [
            ("crushing chest pressure radiating to left arm with cold sweats", "Heart Attack"),
            ("burning upper abdominal ache with acid indigestion and bloating", "Gastritis"),
            ("severe stiff neck inability to touch chin to chest with high fever", "Meningitis"),
            ("wheezing whistling sound when exhaling with shortness of breath", "Asthma"),
            ("painful rash in a single stripe on one side with fluid filled blisters", "Shingles"),
            ("burning pain during urination with frequent intense urge", "UTI"),
        ]
        for symptoms, expected_disease in cases:
            cleaned = clean_text(symptoms)
            X = transform_text(cleaned, self.vectorizer)
            preds = predict_top_k(self.model, X, k=3)
            top_disease, conf = preds[0]
            top_3_diseases = [p[0] for p in preds]
            self.assertIn(
                expected_disease,
                top_3_diseases,
                f"Expected '{expected_disease}' in Top-3 for '{symptoms}'. Got: {top_3_diseases}"
            )
            self.assertEqual(top_disease, expected_disease)
            self.assertGreaterEqual(conf, 0.30)

    def test_04_urdu_clinical_predictions(self):
        cases = [
            ("سینے پر شدید بوجھ اور دباؤ بائیں بازو میں درد ٹھنڈے پسینے", "Heart Attack"),
            ("گردن میں شدید اکڑن تیز بخار ناقابل برداشت سر درد", "Meningitis"),
            ("پیشاب کرتے وقت شدید جلن اور بار بار پیشاب کی حاجت", "UTI"),
            ("چھینکیں آنا ناک بہنا ہلکا بخار گلے میں خراش", "Common Cold"),
            ("جوڑوں میں شدید درد اور صبح کے وقت اکڑن سوجن", "Arthritis"),
        ]
        for symptoms, expected_disease in cases:
            cleaned = clean_text(symptoms)
            X = transform_text(cleaned, self.vectorizer)
            preds = predict_top_k(self.model, X, k=3)
            top_disease, conf = preds[0]
            top_3_diseases = [p[0] for p in preds]
            self.assertIn(
                expected_disease,
                top_3_diseases,
                f"Expected '{expected_disease}' in Top-3 for Urdu symptoms '{symptoms}'. Got: {top_3_diseases}"
            )
            self.assertEqual(top_disease, expected_disease)
            self.assertGreaterEqual(conf, 0.30)

    def test_05_emergency_triage_alignment(self):
        # Heart Attack symptoms must always receive High triage
        cleaned = clean_text("severe chest pain radiating to jaw and arm with shortness of breath")
        X = transform_text(cleaned, self.vectorizer)
        preds = predict_top_k(self.model, X, k=3)
        top_disease, conf = preds[0]
        triage = generate_triage(top_disease, conf, cleaned)
        self.assertEqual(triage["triage_level"], "High")


if __name__ == "__main__":
    unittest.main()
