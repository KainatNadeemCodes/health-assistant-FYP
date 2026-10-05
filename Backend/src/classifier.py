"""
src/classifier.py
==================
AI-Powered Smart Health Assistant | Version 1.2
Purpose: core prediction engine for symptom classification.
"""
import os
import pickle
import logging
import numpy as np

log = logging.getLogger(__name__)
DEFAULT_MODEL_PATH = os.path.join("models", "model.pkl")
_MODEL_CACHE: dict = {}

def load_model(path: str = DEFAULT_MODEL_PATH):
    if path in _MODEL_CACHE:
        return _MODEL_CACHE[path]

    if not os.path.exists(path):
        raise FileNotFoundError(f"Model not found at '{path}'")

    try:
        with open(path, "rb") as f:
            payload = pickle.load(f)
            
        if isinstance(payload, dict) and 'model' in payload:
            model = payload['model']
        else:
            model = payload
            
    except Exception as exc:
        raise RuntimeError(f"Failed to load model: {exc}") from exc

    _MODEL_CACHE[path] = model
    return model

def predict_top_k(model, vectorized_input: np.ndarray, k: int = 3) -> list:
    """
    SRS Traceability:
    FR3 - Symptom-to-Condition Translation
    FR5 - Top-K Accuracy
    """
    if model is None:
        raise TypeError("model is None.")

    if not hasattr(model, "predict_proba"):
        # This error triggers if 'vectorized_input' is passed as the first arg
        raise TypeError(f"Model {type(model).__name__} lacks predict_proba().")

    # Ensure we have a 2D array for sklearn
    if vectorized_input.ndim == 1:
        vectorized_input = vectorized_input.reshape(1, -1)

    probabilities = model.predict_proba(vectorized_input)[0]
    labels = np.asarray(model.classes_)

    k_clamped = min(k, len(probabilities))
    top_indices = np.argpartition(probabilities, -k_clamped)[-k_clamped:]
    top_indices = top_indices[np.argsort(probabilities[top_indices])[::-1]]

    return [(str(labels[i]), round(float(probabilities[i]), 2)) for i in top_indices]

def get_class_labels(model) -> list:
    if model is None: return []
    return [str(c) for c in getattr(model, "classes_", [])]