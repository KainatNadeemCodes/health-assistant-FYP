"""
src/feature_extraction.py
=========================
AI-Powered Smart Health Assistant  |  Version 1.0  |  Group: F25PROJECT664B0

Overview
--------
This module handles the conversion of cleaned symptom text into
numerical features using the same TF-IDF vectorizer that was used
during model training.

Keeping the training and prediction vectorizer consistent is critical
to maintaining model accuracy.

SRS Traceability
----------------
FR3  Symptom-to-Condition Translation — text is converted into the
     numerical format expected by the trained classifier.

FR5  >= 80% Top-3 Accuracy — depends on using the exact vectorizer
     that was fitted during training.
"""

import os
import pickle
import logging

import numpy as np

# Module-specific logger (configured centrally in main application)
log = logging.getLogger(__name__)

# Default location of the trained TF-IDF vectorizer
DEFAULT_VECTORIZER_PATH = os.path.join("models", "vectorizer.pkl")

# Cache to avoid loading the same vectorizer repeatedly from disk
_VECTORIZER_CACHE: dict = {}


# ===========================================================================
# PUBLIC API
# ===========================================================================

def load_vectorizer(path: str = DEFAULT_VECTORIZER_PATH):
    """
    Load a pre-trained TF-IDF vectorizer from disk.

    The vectorizer is cached after the first load so repeated calls
    do not perform unnecessary disk reads.

    Parameters
    ----------
    path : str
        Path to the saved vectorizer file.
        Defaults to 'models/vectorizer.pkl'.

    Returns
    -------
    A fitted sklearn TfidfVectorizer instance.

    Raises
    ------
    FileNotFoundError  If the file does not exist.
    RuntimeError       If loading fails.
    ValueError         If the object is not a valid fitted vectorizer.
    """

    # Return cached instance if already loaded
    if path in _VECTORIZER_CACHE:
        log.debug("Returning cached vectorizer for '%s'.", path)
        return _VECTORIZER_CACHE[path]

    # Ensure file exists before attempting load
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Vectorizer not found at '{path}'.\n"
            "Run train_model.py first to generate models/vectorizer.pkl."
        )

    # Attempt safe deserialization
    try:
        with open(path, "rb") as f:
            vectorizer = pickle.load(f)
    except (pickle.UnpicklingError, EOFError, Exception) as exc:
        raise RuntimeError(
            f"Failed to load vectorizer from '{path}': {exc}"
        ) from exc

    # Basic validation to ensure this is a fitted TF-IDF vectorizer
    if not hasattr(vectorizer, "transform") or not hasattr(vectorizer, "vocabulary_"):
        raise ValueError(
            f"Object at '{path}' is not a fitted sklearn vectorizer "
            "(missing 'transform' or 'vocabulary_')."
        )

    log.info(
        "Vectorizer loaded | path='%s' | vocabulary size=%d",
        path, len(vectorizer.vocabulary_),
    )

    _VECTORIZER_CACHE[path] = vectorizer
    return vectorizer


def transform_text(text: str, vectorizer) -> np.ndarray:
    """
    Convert a cleaned symptom string into a 2-D TF-IDF feature array.

    The input text should already be preprocessed (lowercased,
    tokenized, cleaned) before being passed here.

    Parameters
    ----------
    text        : str — cleaned symptom text (e.g., "fever sore throat").
    vectorizer  : Fitted TfidfVectorizer from load_vectorizer().

    Returns
    -------
    np.ndarray  Dense array of shape (1, n_features).

    Raises
    ------
    TypeError   If vectorizer is missing or invalid.
    ValueError  If text is empty or not a valid string.
    """

    if vectorizer is None:
        raise TypeError(
            "vectorizer is None. Call load_vectorizer() before transforming text."
        )

    if not hasattr(vectorizer, "transform"):
        raise TypeError(
            f"Expected a fitted sklearn vectorizer, "
            f"got '{type(vectorizer).__name__}' without 'transform'."
        )

    if not isinstance(text, str) or not text.strip():
        raise ValueError(
            "Text is empty or invalid. Ensure preprocessing was applied correctly."
        )

    # Transform text to sparse matrix, then convert to dense array
    dense = vectorizer.transform([text]).toarray()

    log.debug(
        "transform_text | input='%.50s' | shape=%s | non-zero=%d",
        text, dense.shape, int((dense > 0).sum()),
    )

    return dense


def get_feature_names(vectorizer) -> list:
    """
    Return the ordered list of feature (token) names from the vectorizer.

    This is mainly used by the explainability module to map
    feature indices back to readable symptom tokens.

    Returns an empty list if vectorizer is None or invalid.
    """

    if vectorizer is None:
        return []

    if hasattr(vectorizer, "get_feature_names_out"):
        return list(vectorizer.get_feature_names_out())

    if hasattr(vectorizer, "get_feature_names"):
        return list(vectorizer.get_feature_names())

    vocab = getattr(vectorizer, "vocabulary_", {})
    if vocab:
        return [tok for tok, _ in sorted(vocab.items(), key=lambda x: x[1])]

    return []


# ===========================================================================
# SMOKE TEST  (Run: python -m src.feature_extraction)
# ===========================================================================

if __name__ == "__main__":
    """
    Quick manual tests to verify:
    - Vectorizer loading
    - Cache behavior
    - Text transformation
    - Feature name extraction
    - Error handling
    """

    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    print("\n" + "=" * 65)
    print(" src/feature_extraction.py — Smoke-Test")
    print("=" * 65 + "\n")

    VEC_PATH = os.path.join("models", "vectorizer.pkl")

    print("-- Test 1: load_vectorizer() --")
    try:
        vec = load_vectorizer(VEC_PATH)
        print(f"  Type        : {type(vec).__name__}")
        print(f"  Vocab size  : {len(vec.vocabulary_)}")
        print(f"  PASS\n")
    except FileNotFoundError:
        print(f"  Not found at '{VEC_PATH}'. Run train_model.py first.  SKIP\n")
        sys.exit(0)

    print("-- Test 2: cache verification --")
    vec2 = load_vectorizer(VEC_PATH)
    assert vec is vec2
    print(f"  Same object returned from cache: True  PASS\n")

    print("-- Test 3: transform_text() --")
    for sym in ["fever sore throat", "chest pain shortness breath"]:
        out = transform_text(sym, vec)
        print(f"  [{out.shape}] non-zero={int((out>0).sum())}  {sym}")
    print(f"  PASS\n")

    print("-- Test 4: get_feature_names() --")
    names = get_feature_names(vec)
    print(f"  Features: {len(names)}  first 5: {names[:5]}  PASS\n")

    print("-- Test 5: FileNotFoundError handling --")
    try:
        load_vectorizer("models/does_not_exist.pkl")
        print("  FAIL")
    except FileNotFoundError:
        print("  FileNotFoundError raised correctly  PASS\n")

    print("=" * 65)
    print(" All tests completed successfully.")
    print("=" * 65 + "\n")