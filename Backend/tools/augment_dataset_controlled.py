#!/usr/bin/env python3
"""Create controlled, deterministic symptom paraphrases.

The script only replaces phrases listed in symptom_synonyms.json. It does not
invent symptoms, add diagnoses, translate text, or modify the original rows.
Each generated row retains the original base_sample_id for leakage-safe splits.

Run from Backend:
    python tools/augment_dataset_controlled.py \
      --input data/dataset_v1_metadata.csv \
      --synonyms data/symptom_synonyms.json \
      --output data/dataset_v2_augmented.csv \
      --variants-per-record 2
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {
    "sample_id", "base_sample_id", "disease", "symptoms", "language",
    "input_style", "source_type", "severity", "red_flag",
    "review_status", "review_notes",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Controlled synonym augmentation")
    parser.add_argument("--input", required=True, help="Input metadata CSV")
    parser.add_argument("--synonyms", required=True, help="Synonym JSON dictionary")
    parser.add_argument("--output", required=True, help="Output augmented CSV")
    parser.add_argument("--variants-per-record", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def phrase_pattern(phrase: str) -> re.Pattern[str]:
    # Match phrases as complete word sequences, including flexible whitespace.
    escaped = re.escape(phrase.strip()).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![A-Za-z]){escaped}(?![A-Za-z])", flags=re.IGNORECASE)


def apply_replacements(text: str, replacements: list[tuple[str, str]]) -> str:
    result = text
    for source, target in replacements:
        result = phrase_pattern(source).sub(target, result, count=1)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def candidate_replacements(text: str, synonym_map: dict[str, list[str]]) -> list[tuple[str, list[str]]]:
    candidates = []
    for source, alternatives in synonym_map.items():
        if phrase_pattern(source).search(text):
            usable = [str(x).strip() for x in alternatives if str(x).strip() and str(x).strip().casefold() != source.casefold()]
            if usable:
                candidates.append((source, usable))
    # Longer phrases first prevents a short phrase from interfering with a
    # longer, more specific phrase.
    return sorted(candidates, key=lambda item: len(item[0]), reverse=True)


def make_variant(text: str, candidates: list[tuple[str, list[str]]], rng: random.Random, variant_number: int) -> str:
    if not candidates:
        return text
    # One replacement for variant 1; at most two for later variants. This keeps
    # the generated text close to the original and makes the change auditable.
    max_replacements = 1 if variant_number == 1 else 2
    selected = candidates[:]
    rng.shuffle(selected)
    selected = selected[:max_replacements]
    replacements = [(source, rng.choice(alternatives)) for source, alternatives in selected]
    return apply_replacements(text, replacements)


def main() -> None:
    args = parse_args()
    if args.variants_per_record < 1:
        raise ValueError("--variants-per-record must be at least 1")

    input_path = Path(args.input).expanduser().resolve()
    synonyms_path = Path(args.synonyms).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_path, keep_default_na=False)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Input metadata is missing columns: {sorted(missing)}")
    with synonyms_path.open(encoding="utf-8") as handle:
        synonym_map: dict[str, list[str]] = json.load(handle)

    rng = random.Random(args.seed)
    records: list[dict[str, Any]] = []
    generated_count = 0
    skipped_no_candidate = 0

    for _, row in df.iterrows():
        original = row.to_dict()
        original["source_type"] = "fyp_original"
        original["review_status"] = original.get("review_status") or "original_unreviewed"
        records.append(original)

        # Only create English controlled variants. The current synonym file is
        # English; Urdu/mixed-language augmentation requires a separate reviewed
        # bilingual dictionary and is intentionally not attempted here.
        if str(row["language"]) != "English":
            continue
        text = str(row["symptoms"]).strip()
        candidates = candidate_replacements(text, synonym_map)
        if not candidates:
            skipped_no_candidate += 1
            continue

        seen = {text.casefold()}
        created_for_row = 0
        for variant_number in range(1, args.variants_per_record + 1):
            variant = make_variant(text, candidates, rng, variant_number)
            if variant.casefold() in seen:
                continue
            seen.add(variant.casefold())
            generated_count += 1
            created_for_row += 1
            item = row.to_dict()
            item["sample_id"] = f"{row['base_sample_id']}_A{created_for_row:02d}"
            item["base_sample_id"] = row["base_sample_id"]
            item["symptoms"] = variant
            item["input_style"] = "controlled_synonym_paraphrase"
            item["source_type"] = "controlled_synonym_augmentation"
            item["review_status"] = "pending_review"
            item["review_notes"] = f"Generated from {row['sample_id']} using approved synonym dictionary; seed={args.seed}."
            records.append(item)

    result = pd.DataFrame(records, columns=list(df.columns))
    result.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Augmented dataset written to: {output_path}")
    print(f"Original rows retained: {len(df)}")
    print(f"Generated rows: {generated_count}")
    print(f"Total rows: {len(result)}")
    print(f"English rows without a matching dictionary phrase: {skipped_no_candidate}")
    print("Original input file was not modified.")


if __name__ == "__main__":
    main()
