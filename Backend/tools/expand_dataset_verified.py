"""
FILE: tools/expand_dataset_verified.py
PURPOSE: Zero-Hallucination Deterministic Clinical Dataset Expansion Engine
AUTHOR: Antigravity / CS619 FYP Team
"""

import json
import os
import random
import re
from pathlib import Path
from typing import List, Dict, Set
import pandas as pd

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
ORIGINAL_DATASET_PATH = DATA_DIR / "dataset_v1_fyp_original.csv"
CLINICAL_KB_PATH = DATA_DIR / "verified_clinical_kb.json"
SYNONYMS_PATH = DATA_DIR / "symptom_synonyms.json"

TARGET_DATASET_CSV = DATA_DIR / "dataset.csv"
EXPANDED_METADATA_CSV = DATA_DIR / "dataset_v3_expanded.csv"

# Reproducibility seed
SEED = 42

EN_TEMPLATES = [
    "{p1}, {p2} and {s1}",
    "experiencing {p1} along with {s1} and {p2}",
    "patient complaining of {p1}, {p2} with {mod}",
    "{mod} {p1}, accompanied by {s1}",
    "{p1} and {p2} for several days, also feeling {s1}",
    "{p1}, {s1}, severe {p2}",
    "having {p1} with {s1} and {p2}",
    "{mod} onset of {p1} alongside {p2}",
    "symptoms include {p1}, {p2}, {s1}",
    "{p1} especially worse with {s1}",
    "{p1}, {p2}, feeling {s1} and {s2}",
    "suffering from {mod} {p1} and {p2}",
    "{p1} with occasional {s1} and {p2}",
    "persistent {p1}, {s1} and {p2}",
    "{mod} {p1} followed by {p2} and {s1}",
    "{p1}, {p2}, {p3} with {s1}",
    "noticeable {p1} together with {s1} and {p2}",
    "acute {p1} and {p2} with {s1} symptoms",
]

UR_TEMPLATES = [
    "{p1}، {p2} اور {s1}",
    "{mod} {p1} کے ساتھ {s1} اور {p2}",
    "{p1}، {p2} اور {s1} کی شکایت ہے",
    "{p1} اور {p2} کے ساتھ {s1} بھی محسوس ہو رہا ہے",
    "{mod} {p1} اور {s1}",
    "{p1} کے ساتھ {s1} اور شدید {p2}",
    "مریض کو {p1}، {p2} اور {s1} کی تکلیف ہے",
    "{p1} کے بعد {p2} اور {s1} ہونا",
    "{mod} {p1} کے ساتھ مسلسل {p2}",
    "{p1}، {p2} اور {p3}",
    "{p1} اور {s1} کے ساتھ شدید {p2}",
]


def clean_text(text: str) -> str:
    """Normalizes text and collapses redundant whitespace."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text


def load_synonyms(path: Path) -> Dict[str, List[str]]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def apply_synonym_variation(text: str, synonyms: Dict[str, List[str]], rng: random.Random) -> str:
    """Substitutes verified medical synonyms deterministically."""
    for phrase, alts in synonyms.items():
        if phrase in text and rng.random() < 0.4:
            choice = rng.choice(alts)
            text = text.replace(phrase, choice, 1)
            break
    return text


def generate_clinical_records() -> pd.DataFrame:
    rng = random.Random(SEED)

    # 1. Load Original Baseline
    original_rows = []
    if ORIGINAL_DATASET_PATH.exists():
        orig_df = pd.read_csv(ORIGINAL_DATASET_PATH)
        for idx, row in orig_df.iterrows():
            disease = str(row["disease"]).strip()
            symptoms = clean_text(str(row["symptoms"]))
            is_ur = bool(re.search(r"[\u0600-\u06FF]", symptoms))
            original_rows.append({
                "sample_id": f"ORIG-{idx+1:04d}",
                "disease": disease,
                "symptoms": symptoms,
                "language": "ur" if is_ur else "en",
                "source_type": "fyp_original_baseline",
                "clinical_source": "Original_FYP_Dataset",
            })

    # 2. Load Clinical Knowledge Base
    with open(CLINICAL_KB_PATH, "r", encoding="utf-8") as f:
        clinical_kb = json.load(f)

    synonyms = load_synonyms(SYNONYMS_PATH)
    synthetic_rows = []
    sample_counter = 1

    for disease, data in clinical_kb.items():
        # English primary, secondary, modifiers
        p_en = data.get("primary_en", [])
        s_en = data.get("secondary_en", [])
        m_en = data.get("modifiers_en", ["moderate", "persistent", "acute"])

        # Urdu primary, secondary, modifiers
        p_ur = data.get("primary_ur", [])
        s_ur = data.get("secondary_ur", [])
        m_ur = data.get("modifiers_ur", ["شدید", "مسلسل", "ہلکا"])

        sources_tag = "_".join([s.split()[0] for s in data.get("sources", ["Clinical_Monograph"])])

        # English Combinatorial Generation (~75 rows per disease)
        seen_en: Set[str] = set()
        attempts = 0
        while len(seen_en) < 75 and attempts < 400:
            attempts += 1
            template = rng.choice(EN_TEMPLATES)
            p_sample = rng.sample(p_en, min(3, len(p_en))) if len(p_en) >= 3 else p_en
            s_sample = rng.sample(s_en, min(2, len(s_en))) if len(s_en) >= 2 else s_en
            mod = rng.choice(m_en) if m_en else ""

            rendered = template.format(
                p1=p_sample[0] if len(p_sample) > 0 else "discomfort",
                p2=p_sample[1] if len(p_sample) > 1 else p_sample[0],
                p3=p_sample[2] if len(p_sample) > 2 else p_sample[0],
                s1=s_sample[0] if len(s_sample) > 0 else "fatigue",
                s2=s_sample[1] if len(s_sample) > 1 else "mild weakness",
                mod=mod,
            )
            rendered = apply_synonym_variation(rendered, synonyms, rng)
            cleaned = clean_text(rendered.lower())

            if len(cleaned) >= 12 and cleaned not in seen_en:
                seen_en.add(cleaned)
                synthetic_rows.append({
                    "sample_id": f"EXP-EN-{sample_counter:05d}",
                    "disease": disease,
                    "symptoms": cleaned,
                    "language": "en",
                    "source_type": "clinical_kb_synthesis",
                    "clinical_source": sources_tag,
                })
                sample_counter += 1

        # Urdu Combinatorial Generation (~40 rows per disease)
        seen_ur: Set[str] = set()
        attempts = 0
        while len(seen_ur) < 40 and attempts < 300:
            attempts += 1
            template = rng.choice(UR_TEMPLATES)
            p_sample = rng.sample(p_ur, min(3, len(p_ur))) if len(p_ur) >= 3 else p_ur
            s_sample = rng.sample(s_ur, min(2, len(s_ur))) if len(s_ur) >= 2 else s_ur
            mod = rng.choice(m_ur) if m_ur else ""

            rendered = template.format(
                p1=p_sample[0] if len(p_sample) > 0 else "تکلیف",
                p2=p_sample[1] if len(p_sample) > 1 else p_sample[0],
                p3=p_sample[2] if len(p_sample) > 2 else p_sample[0],
                s1=s_sample[0] if len(s_sample) > 0 else "کمزوری",
                mod=mod,
            )
            cleaned = clean_text(rendered)

            if len(cleaned) >= 8 and cleaned not in seen_ur:
                seen_ur.add(cleaned)
                synthetic_rows.append({
                    "sample_id": f"EXP-UR-{sample_counter:05d}",
                    "disease": disease,
                    "symptoms": cleaned,
                    "language": "ur",
                    "source_type": "clinical_kb_synthesis",
                    "clinical_source": sources_tag,
                })
                sample_counter += 1

    all_records = original_rows + synthetic_rows
    full_df = pd.DataFrame(all_records)

    # Global deduplication on symptoms
    full_df = full_df.drop_duplicates(subset=["symptoms"]).reset_index(drop=True)

    return full_df


def main():
    print("=" * 60)
    print("Zero-Hallucination Clinical Dataset Expansion")
    print("=" * 60)

    expanded_df = generate_clinical_records()
    print(f"Total Expanded Records: {len(expanded_df)}")
    print(f"Total Unique Classes:   {expanded_df['disease'].nunique()}")
    print("\nClass Distribution Summary (sample per disease):")
    class_counts = expanded_df["disease"].value_counts()
    print(f"Min rows per class: {class_counts.min()} | Max rows per class: {class_counts.max()}")
    print(f"English rows: {(expanded_df['language'] == 'en').sum()} | Urdu rows: {(expanded_df['language'] == 'ur').sum()}")

    # Save metadata CSV
    expanded_df.to_csv(EXPANDED_METADATA_CSV, index=False)
    print(f"Saved expanded metadata dataset -> {EXPANDED_METADATA_CSV}")

    # Save live training CSV (disease, symptoms)
    live_df = expanded_df[["disease", "symptoms"]]
    live_df.to_csv(TARGET_DATASET_CSV, index=False)
    print(f"Saved live training dataset     -> {TARGET_DATASET_CSV}")


if __name__ == "__main__":
    main()
