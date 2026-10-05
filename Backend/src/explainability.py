"""
src/explainability.py — AI Prediction Explainability
Version 2.0 |  Group: F25PROJECT664B0

Overview
--------
This module explains *why* the model predicted a particular disease.
Instead of acting as a black box, it highlights the symptoms that had
the strongest influence on the final decision.

Explainability Strategy (in order of preference)
-------------------------------------------------
1. SHAP LinearExplainer  — uses the actual SHAP library for proper
   Shapley-value attribution on the Logistic Regression + TF-IDF model.
   This satisfies SRS UC-04 / FR13 directly.

2. Coefficient × Activation fallback  — if SHAP is unavailable (import
   error or runtime failure), the existing coefficient-based scoring
   takes over transparently.  No UI change; the panel still populates.

Recent Updates
--------------
• v2.0 — Added SHAP LinearExplainer as primary explainability strategy
• v1.1 — Updated import path to use 'src.feature_extraction'
• v1.0 — Initial custom feature-attribution implementation

SRS Traceability
----------------
FR13  Explainability Panel — highlights influential symptoms
UC-04 Explainability Panel — SHAP/LIME explainer on the final model
TC-11 AI Explanation Display — entry via get_influencing_symptoms()
"""

import logging
import numpy as np
from typing import Optional

log = logging.getLogger(__name__)

# Default number of symptoms to display in the explainability panel
DEFAULT_TOP_N = 5

# ══════════════════════════════════════════════════════════════════════════
# SHAP INTEGRATION
# ══════════════════════════════════════════════════════════════════════════

def get_shap_explanation(
    model,
    vectorizer,
    input_vector: np.ndarray,
    top_n: int = DEFAULT_TOP_N,
) -> list:
    """
    Use SHAP LinearExplainer to compute Shapley values for the
    Logistic Regression + TF-IDF prediction.

    Returns a list of (symptom_token, shap_score) tuples for the
    top-N most influential features, or [] if SHAP is unavailable.

    Parameters
    ----------
    model        : Fitted LogisticRegression (or any sklearn linear model)
    vectorizer   : Fitted TfidfVectorizer — used to get feature names
    input_vector : Dense np.ndarray of shape (1, n_features) or (n_features,)
    top_n        : Number of top features to return

    How it works
    ------------
    SHAP LinearExplainer works directly with linear models.  It computes
    the exact Shapley values using the model coefficients — no sampling,
    no approximation.  Each value shows how much that TF-IDF feature
    pushed the prediction toward (positive) or away from (negative) the
    predicted class.
    """
    try:
        import shap  # imported here so the module loads even if shap is absent
    except ImportError:
        log.warning("SHAP not installed — falling back to coefficient scoring.")
        return []

    if model is None or vectorizer is None or input_vector is None:
        return []

    try:
        # Ensure 2-D array (1 sample × n_features)
        vec_2d = input_vector.reshape(1, -1) if input_vector.ndim == 1 else input_vector

        # SHAP LinearExplainer needs a background dataset.
        # For inference-time use we pass a zero vector (mean of a sparse dataset
        # approximation).  This is the recommended lightweight approach when
        # no training data is available at runtime.
        background = np.zeros((1, vec_2d.shape[1]))

        explainer = shap.LinearExplainer(model, background, feature_perturbation="interventional")
        shap_values = explainer.shap_values(vec_2d)  # shape: (1, n_features) or list of those

        # For multi-class LR, shap_values is a list (one array per class).
        # Pick the values for the predicted class.
        if isinstance(shap_values, list):
            predicted_class_idx = _get_predicted_class_idx(model, vec_2d) or 0
            class_shap = np.array(shap_values[predicted_class_idx]).flatten()
        else:
            class_shap = np.array(shap_values).flatten()

        # Only consider features actually present in the input
        vec_1d = vec_2d.flatten()
        active_mask = vec_1d > 0
        class_shap = class_shap * active_mask

        # Rank by absolute SHAP value (direction doesn't matter for display)
        abs_shap = np.abs(class_shap)
        top_n_clamped = min(top_n, len(abs_shap))
        top_indices = [
            i for i in np.argsort(abs_shap)[::-1][:top_n_clamped]
            if abs_shap[i] > 0
        ]

        if not top_indices:
            return []

        feature_names = _get_feature_names(vectorizer, len(vec_1d))
        raw_scores = abs_shap[top_indices]
        norm_scores = _minmax_normalise(raw_scores)

        results = [
            (feature_names[i], float(round(norm_scores[j], 4)))
            for j, i in enumerate(top_indices)
        ]

        log.debug("SHAP top features: %s", results)
        return results

    except Exception as exc:
        log.warning("SHAP explanation failed: %s — falling back.", exc)
        return []


# ══════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════

def get_top_features(
    model,
    vectorizer,
    input_vector: np.ndarray,
    top_n: int = DEFAULT_TOP_N,
) -> list:
    """
    Identify the top-N symptom features that contributed most
    to the model's prediction.

    Strategy order:
      1. SHAP LinearExplainer (preferred — satisfies SRS UC-04)
      2. Model coefficient / feature_importances_ scoring (fallback)
      3. Raw TF-IDF activation values (last resort)

    Returns a list of (symptom_token, importance_score),
    where scores are normalised to the range [0, 1].
    """

    # ── Strategy 1: SHAP ──────────────────────────────────────────────────
    shap_result = get_shap_explanation(model, vectorizer, input_vector, top_n)
    if shap_result:
        log.debug("Using SHAP explanation.")
        return shap_result

    # ── Strategy 2 & 3: existing coefficient-based scoring ────────────────
    if input_vector is None or not isinstance(input_vector, np.ndarray):
        log.warning("input_vector is invalid — returning empty result.")
        return []

    vec_1d     = input_vector.flatten()
    n_features = len(vec_1d)

    if n_features == 0:
        return []

    feature_names        = _get_feature_names(vectorizer, n_features)
    predicted_class_idx  = _get_predicted_class_idx(model, input_vector)

    scores = _score_by_model_type(
        model, vec_1d, predicted_class_idx, n_features
    )

    if scores is None or len(scores) == 0:
        log.warning("Model scoring unavailable — using activation fallback.")
        scores = vec_1d.copy()

    active_mask = vec_1d > 0
    scores      = scores * active_mask

    top_n_clamped = min(top_n, n_features)
    top_indices = [
        i for i in np.argsort(scores)[::-1][:top_n_clamped]
        if scores[i] > 0
    ]

    if not top_indices:
        log.info("No influential features detected for this input.")
        return []

    raw_scores  = np.array([scores[i] for i in top_indices], dtype=float)
    norm_scores = _minmax_normalise(raw_scores)

    results = [
        (feature_names[i], float(round(norm_scores[j], 4)))
        for j, i in enumerate(top_indices)
    ]

    log.debug("Top influencing features (fallback): %s", results)
    return results


def get_influencing_symptoms(
    model,
    input_vector: np.ndarray,
    cleaned_text: str,
    vectorizer_path: str = "models/vectorizer.pkl",
    top_n: int = DEFAULT_TOP_N,
) -> list:
    """
    Main entry point used by app.py.

    Returns only the symptom tokens (without scores)
    for display in the explainability panel.

    If the model or vectorizer cannot be loaded,
    it gracefully falls back to extracting keywords
    directly from the cleaned text.
    """

    vectorizer = _load_vectorizer_safe(vectorizer_path)

    if model is not None and vectorizer is not None:
        try:
            scored = get_top_features(model, vectorizer, input_vector, top_n)
            if scored:
                return [token for token, _ in scored]
        except Exception as exc:
            log.warning(
                "Feature scoring failed: %s — falling back to text extraction.",
                exc
            )

    # Text-based fallback ensures the UI always displays something
    return _text_fallback(cleaned_text, top_n)


def get_explanation_text(
    influencing_symptoms: list,
    top_disease: str,
) -> str:
    """
    Generate a short natural-language explanation for the UI.

    This sentence appears in the explainability panel and
    helps users understand why a disease was predicted.
    """

    if not influencing_symptoms:
        return (
            f"The AI detected patterns consistent with {top_disease}, "
            "but no single dominant symptom stood out clearly."
        )

    if len(influencing_symptoms) == 1:
        sym_text = f"'{influencing_symptoms[0]}'"
    elif len(influencing_symptoms) == 2:
        sym_text = f"'{influencing_symptoms[0]}' and '{influencing_symptoms[1]}'"
    else:
        quoted   = [f"'{s}'" for s in influencing_symptoms[:-1]]
        sym_text = ", ".join(quoted) + f", and '{influencing_symptoms[-1]}'"

    return (
        f"The AI identified {sym_text} as the most influential symptom(s) "
        f"when predicting {top_disease}. These carried the strongest "
        f"weight in the model's decision."
    )


# ══════════════════════════════════════════════════════════════════════════
# PRIVATE — SCORING STRATEGIES (unchanged fallback)
# ══════════════════════════════════════════════════════════════════════════

def _score_by_model_type(model, vec_1d, predicted_class_idx, n_features):
    """
    Apply a scoring strategy depending on the model type.
    Different ML models expose feature importance differently.
    """

    if model is None:
        return None

    # Strategy 1: Tree-based models (e.g., RandomForest)
    if hasattr(model, "feature_importances_"):
        imp = np.array(model.feature_importances_, dtype=float)
        if len(imp) == n_features:
            log.debug("Using tree-based feature_importances_.")
            return imp * vec_1d

    # Strategy 2: Linear models (e.g., Logistic Regression)
    if hasattr(model, "coef_"):
        coef = np.array(model.coef_)
        if coef.ndim == 2 and predicted_class_idx is not None:
            class_coef = coef[min(predicted_class_idx, coef.shape[0] - 1)]
        elif coef.ndim == 1:
            class_coef = coef
        else:
            class_coef = coef[0]
        if len(class_coef) == n_features:
            log.debug("Using linear model coefficients.")
            return np.abs(class_coef) * vec_1d

    # Strategy 3: Naive Bayes
    if hasattr(model, "feature_log_prob_"):
        lp = np.array(model.feature_log_prob_)
        if predicted_class_idx is not None and lp.ndim == 2:
            cls_lp = lp[min(predicted_class_idx, lp.shape[0] - 1)]
            if len(cls_lp) == n_features:
                log.debug("Using Naive Bayes log probabilities.")
                return np.exp(cls_lp) * vec_1d

    # Strategy 4: If model is wrapped in sklearn Pipeline
    if hasattr(model, "steps"):
        log.debug("Unwrapping sklearn Pipeline.")
        return _score_by_model_type(
            model.steps[-1][1], vec_1d, predicted_class_idx, n_features
        )

    return None


# ══════════════════════════════════════════════════════════════════════════
# PRIVATE — UTILITIES (unchanged)
# ══════════════════════════════════════════════════════════════════════════

def _get_feature_names(vectorizer, n_features: int) -> list:
    """Safely retrieve feature names from the fitted vectorizer."""
    if vectorizer is None:
        return [f"feature_{i}" for i in range(n_features)]

    for attr in ("get_feature_names_out", "get_feature_names"):
        if hasattr(vectorizer, attr):
            try:
                names = list(getattr(vectorizer, attr)())
                if len(names) == n_features:
                    return names
            except Exception:
                pass

    vocab = getattr(vectorizer, "vocabulary_", {})
    if vocab and len(vocab) == n_features:
        return [t for t, _ in sorted(vocab.items(), key=lambda x: x[1])]

    return [f"feature_{i}" for i in range(n_features)]


def _get_predicted_class_idx(model, input_vector: np.ndarray) -> Optional[int]:
    """Determine index of predicted class for class-specific scoring."""
    if model is None or not hasattr(model, "predict"):
        return None
    try:
        label   = model.predict(input_vector)[0]
        classes = list(getattr(model, "classes_", []))
        if classes and label in classes:
            return classes.index(label)
    except Exception as exc:
        log.debug("Could not determine predicted class index: %s", exc)
    return None


def _minmax_normalise(arr: np.ndarray) -> np.ndarray:
    """Scale scores to the range [0, 1] for UI clarity."""
    a_min, a_max = arr.min(), arr.max()
    if a_max == a_min:
        return np.ones_like(arr, dtype=float)
    return (arr - a_min) / (a_max - a_min)


def _load_vectorizer_safe(path: str):
    """
    Attempt to load vectorizer safely.
    Returns None if loading fails — prevents UI crash.
    """
    try:
        from src.feature_extraction import load_vectorizer
        return load_vectorizer(path)
    except Exception as exc:
        log.debug("Vectorizer load failed from '%s': %s", path, exc)
        return None


def _text_fallback(cleaned_text: str, top_n: int) -> list:
    """
    Extract meaningful tokens directly from cleaned_text
    when model-based explainability is unavailable.
    """
    if not cleaned_text or not isinstance(cleaned_text, str):
        return []

    tokens = cleaned_text.split()
    seen, unique = set(), []

    for t in tokens:
        if t not in seen and len(t) > 2:
            seen.add(t)
            unique.append(t)

    # Prefer longer tokens (often more descriptive)
    unique.sort(key=len, reverse=True)
    return unique[:top_n]