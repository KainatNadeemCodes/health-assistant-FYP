#!/usr/bin/env python3
"""Create a versioned metadata table for the original FYP dataset.

This script does not alter the original dataset. It creates a separate CSV with
stable IDs and research metadata for later augmentation and leakage-safe splits.

Run from the Backend directory:
    python tools/prepare_dataset_metadata.py \
        --input data/dataset_v1_fyp_original.csv \
        --output data/dataset_v1_metadata.csv
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

URDU_RE = re.compile(r"[\u0600-\u06FF]")
LATIN_RE = re.compile(r"[A-Za-z]")


def classify_language(text: str) -> str:
    text = str(text)
    has_urdu = bool(URDU_RE.search(text))
    has_latin = bool(LATIN_RE.search(text))
    if has_urdu and has_latin:
        return "Mixed"
    if has_urdu:
        return "Urdu-script"
    if has_latin:
        return "English"
    return "Other/Unclassified"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare dataset metadata.")
    parser.add_argument("--input", required=True, help="Input CSV with disease,symptoms columns")
    parser.add_argument("--output", required=True, help="Output metadata CSV")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path)
    required = {"disease", "symptoms"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    records = []
    for index, row in df.iterrows():
        symptoms = str(row["symptoms"]).strip()
        language = classify_language(symptoms)
        input_style = {
            "English": "original_english",
            "Urdu-script": "original_urdu_script",
            "Mixed": "original_mixed",
        }.get(language, "original_other")
        sample_id = f"FYP_{index + 1:04d}"
        records.append(
            {
                "sample_id": sample_id,
                "base_sample_id": sample_id,
                "disease": str(row["disease"]).strip(),
                "symptoms": symptoms,
                "language": language,
                "input_style": input_style,
                "source_type": "fyp_original",
                "severity": "pending_review",
                "red_flag": "pending_review",
                "review_status": "original_unreviewed",
                "review_notes": "",
            }
        )

    metadata = pd.DataFrame(records)
    metadata.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Metadata written to: {output_path}")
    print(f"Records: {len(metadata)}")
    print(f"Languages: {metadata['language'].value_counts().to_dict()}")
    print("Original dataset was not modified.")


if __name__ == "__main__":
    main()
