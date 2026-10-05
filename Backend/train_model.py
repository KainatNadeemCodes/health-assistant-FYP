"""
train_model.py
==============
AI-Powered Smart Health Assistant  |  Version 1.0 |  Group: F25PROJECT664B0

This script trains the machine learning model used for symptom classification.
It performs:

1. Data loading and cleaning
2. Text preprocessing (same logic as the live app)
3. TF-IDF feature extraction
4. Logistic Regression training
5. Evaluation (Top-1 and Top-3 accuracy)
6. Saving the trained model and vectorizer

Run:
    python train_model.py

Outputs:
    models/model.pkl
    models/vectorizer.pkl
"""

import os
import pickle
import logging
import warnings

import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report


# ---------------------------------------------------------------------------
# Import the same preprocessing function used in the live application.
# This ensures consistency between training and prediction.
# ---------------------------------------------------------------------------

try:
    from src.preprocessing import clean_text as preprocess_text
    _USING_SRC_PREPROCESSING = True
except ImportError:
    import re
    import warnings as _w
    _w.warn(
        "Could not import src.preprocessing.clean_text. "
        "Using fallback text cleaner.",
        ImportWarning,
        stacklevel=2,
    )
    _USING_SRC_PREPROCESSING = False

    def preprocess_text(text: str) -> str:
        text = str(text).strip()
        import re
        text = re.sub(r"\s+", " ", text)
        return text.lower()


# Silence non-critical warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s]  %(message)s",
)
log = logging.getLogger(__name__)


# Paths
DATA_PATH = os.path.join("data", "dataset.csv")
MODEL_DIR = "models"
MODEL_PATH = os.path.join(MODEL_DIR, "model.pkl")
VECTORIZER_PATH = os.path.join(MODEL_DIR, "vectorizer.pkl")

# Hyperparameters
TEST_SIZE = 0.20
RANDOM_STATE = 42
TOP_K = 3


# ===========================================================================
# STEP 1 — LOAD DATA
# ===========================================================================

def load_data(path: str) -> pd.DataFrame:
    """
    Load dataset and perform basic validation.

    Ensures:
    - File exists
    - Required columns are present
    - Null and duplicate rows are removed
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Dataset not found at '{path}'. Place dataset.csv inside data/."
        )

    log.info("Loading dataset from '%s' ...", path)
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    required = {"symptoms", "disease"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required columns: {missing}. Found: {list(df.columns)}"
        )

    before = len(df)
    df = df.dropna(subset=["symptoms", "disease"])
    df = df.drop_duplicates(subset=["symptoms"])
    removed = before - len(df)

    if removed:
        log.warning("Removed %d null/duplicate rows.", removed)

    df["symptoms"] = df["symptoms"].astype(str).str.strip()
    df["disease"] = df["disease"].astype(str).str.strip()

    log.info(
        "Dataset ready: %d rows | %d classes",
        len(df), df["disease"].nunique(),
    )

    return df


# ===========================================================================
# STEP 2 — BUILD VECTORIZER AND CLASSIFIER
# ===========================================================================

def build_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=5000,
        sublinear_tf=True,
        min_df=1,
        strip_accents=None,
        token_pattern=r"(?u)\b[\w\u0600-\u06FF][\w\u0600-\u06FF]+\b",
    )


def build_classifier() -> LogisticRegression:
    """
    Create Logistic Regression classifier.

    - Handles multi-class classification.
    - class_weight='balanced' helps with imbalanced datasets.
    - max_iter increased to ensure convergence.
    """
    return LogisticRegression(
        solver="lbfgs",
        C=1.0,
        max_iter=1000,
        class_weight="balanced",
        random_state=RANDOM_STATE,
    )


# ===========================================================================
# STEP 3 — TRAIN
# ===========================================================================

def train(X_train, y_train, vectorizer, classifier):
    """
    Train vectorizer and classifier.

    Vectorizer is fitted ONLY on training data to avoid data leakage.
    """
    log.info("Fitting TF-IDF vectorizer...")
    X_train_tfidf = vectorizer.fit_transform(X_train)
    log.info("Vocabulary size: %d features", len(vectorizer.vocabulary_))

    log.info("Training Logistic Regression...")
    classifier.fit(X_train_tfidf, y_train)

    return vectorizer, classifier, X_train_tfidf


# ===========================================================================
# STEP 4 — EVALUATE
# ===========================================================================

def evaluate(classifier, vectorizer, X_train, X_test, y_train, y_test) -> dict:
    """
    Evaluate model performance.

    Reports:
    - Training accuracy
    - Test Top-1 accuracy
    - Test Top-3 accuracy
    - Detailed classification report
    """
    X_train_tfidf = vectorizer.transform(X_train)
    X_test_tfidf = vectorizer.transform(X_test)

    y_pred_train = classifier.predict(X_train_tfidf)
    y_pred_test = classifier.predict(X_test_tfidf)
    y_proba_test = classifier.predict_proba(X_test_tfidf)

    train_acc = accuracy_score(y_train, y_pred_train)
    test_acc = accuracy_score(y_test, y_pred_test)
    top_k_acc = _top_k_accuracy(
        y_test.values, y_proba_test, classifier.classes_, k=TOP_K
    )

    _section("EVALUATION RESULTS")
    print(f"  Training Accuracy     :  {train_acc * 100:>6.2f}%")
    print(f"  Test Accuracy (Top-1) :  {test_acc * 100:>6.2f}%")
    print(f"  Test Accuracy (Top-{TOP_K}) :  {top_k_acc * 100:>6.2f}%")

    _section("CLASSIFICATION REPORT")
    print(classification_report(y_test, y_pred_test, digits=4))

    return {
        "train_accuracy": round(train_acc, 4),
        "test_accuracy": round(test_acc, 4),
        "top3_accuracy": round(top_k_acc, 4),
    }


def _top_k_accuracy(y_true, y_proba, classes, k) -> float:
    """
    Compute Top-K accuracy.
    Checks whether true label appears in top K predictions.
    """
    correct = sum(
        1 for true, probs in zip(y_true, y_proba)
        if true in classes[np.argsort(probs)[::-1][:k]]
    )
    return correct / len(y_true)


# ===========================================================================
# STEP 5 — SAVE MODEL
# ===========================================================================

def save_artefacts(
    classifier,
    vectorizer,
    model_path: str = MODEL_PATH,
    vec_path: str = VECTORIZER_PATH,
) -> None:
    """
    Save trained model and vectorizer to disk.
    """
    os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)

    log.info("Saving model...")
    with open(model_path, "wb") as f:
        pickle.dump(classifier, f, protocol=pickle.HIGHEST_PROTOCOL)

    log.info("Saving vectorizer...")
    with open(vec_path, "wb") as f:
        pickle.dump(vectorizer, f, protocol=pickle.HIGHEST_PROTOCOL)


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def main() -> None:

    _section("MODEL TRAINING PIPELINE")

    # 1. Load data
    df = load_data(DATA_PATH)

    # 2. Preprocess text
    log.info("Preprocessing symptom text...")
    df["symptoms_clean"] = df["symptoms"].apply(preprocess_text)

    X = df["symptoms_clean"]
    y = df["disease"]

    # 3. Train-test split (stratified to preserve class distribution)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    # 4. Build model components
    vectorizer = build_vectorizer()
    classifier = build_classifier()

    # 5. Train
    vectorizer, classifier, _ = train(X_train, y_train, vectorizer, classifier)

    # 6. Evaluate
    metrics = evaluate(classifier, vectorizer, X_train, X_test, y_train, y_test)

    # 7. Save trained artefacts
    save_artefacts(classifier, vectorizer)

    _section("TRAINING COMPLETE")
    print(f"Top-1 Accuracy : {metrics['test_accuracy'] * 100:.2f}%")
    print(f"Top-3 Accuracy : {metrics['top3_accuracy'] * 100:.2f}%")
    print("Model and vectorizer saved to models/ directory.")


def _section(title: str, width: int = 60) -> None:
    pad = max(0, width - len(title) - 4)
    left = pad // 2
    right = pad - left
    print()
    print("  " + "=" * left + f"  {title}  " + "=" * right)
    print()


if __name__ == "__main__":
    main()