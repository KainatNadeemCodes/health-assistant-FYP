#!/usr/bin/env python3
"""Verify controlled augmentation quality and distribution.

Run from Backend:
    python tools/verify_augmented_dataset.py \
      --original data/dataset_v1_metadata.csv \
      --augmented data/dataset_v2_augmented.csv \
      --output audit_reports/augmentation_quality_report.md
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

REQUIRED = {
    "sample_id", "base_sample_id", "disease", "symptoms", "language",
    "input_style", "source_type", "severity", "red_flag",
    "review_status", "review_notes",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Verify augmented dataset quality")
    p.add_argument("--original", required=True, help="Original metadata CSV")
    p.add_argument("--augmented", required=True, help="Augmented metadata CSV")
    p.add_argument("--output", required=True, help="Markdown report path")
    p.add_argument("--class-csv", default=None, help="Optional class-distribution CSV path")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    original_path = Path(args.original).expanduser().resolve()
    augmented_path = Path(args.augmented).expanduser().resolve()
    report_path = Path(args.output).expanduser().resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)

    original = pd.read_csv(original_path, keep_default_na=False)
    augmented = pd.read_csv(augmented_path, keep_default_na=False)
    missing = REQUIRED - set(augmented.columns)
    if missing:
        raise ValueError(f"Augmented dataset missing columns: {sorted(missing)}")

    flags: list[str] = []
    original_ids = set(original["sample_id"])
    original_base_ids = set(original["base_sample_id"])
    generated = augmented[augmented["source_type"] != "fyp_original"].copy()
    retained = augmented[augmented["source_type"] == "fyp_original"].copy()

    checks = {
        "original_rows_retained": len(retained) == len(original),
        "original_sample_ids_retained": set(retained.sample_id) == original_ids,
        "original_base_ids_retained": set(retained.base_sample_id) == original_base_ids,
        "unique_sample_ids": augmented.sample_id.is_unique,
        "nonempty_symptoms": bool(augmented.symptoms.astype(str).str.strip().ne("").all()),
        "same_class_count": augmented.disease.nunique() == original.disease.nunique(),
        "generated_has_parent": bool(generated.base_sample_id.isin(original_base_ids).all()),
        "generated_is_not_original_source": bool((generated.source_type == "fyp_original").sum() == 0),
        "generated_review_pending": bool((generated.review_status == "pending_review").all()) if len(generated) else True,
        "generated_keeps_language": bool((generated.language == "English").all()) if len(generated) else True,
    }
    for name, passed in checks.items():
        if not passed:
            flags.append(name)

    parent = original.set_index("sample_id")
    unchanged_generated = 0
    wrong_parent_class = 0
    for _, row in generated.iterrows():
        if row["base_sample_id"] not in parent.index:
            continue
        p = parent.loc[row["base_sample_id"]]
        if str(row["symptoms"]).casefold() == str(p["symptoms"]).casefold():
            unchanged_generated += 1
        if row["disease"] != p["disease"]:
            wrong_parent_class += 1
    if unchanged_generated:
        flags.append("generated_text_unchanged")
    if wrong_parent_class:
        flags.append("generated_parent_class_mismatch")

    duplicate_symptom_rows = int(augmented["symptoms"].astype(str).str.casefold().duplicated().sum())
    duplicate_sample_ids = int(augmented["sample_id"].duplicated().sum())
    group_sizes = augmented.groupby("base_sample_id").size()
    max_group_size = int(group_sizes.max()) if len(group_sizes) else 0
    groups_with_more_than_three = int((group_sizes > 3).sum())
    if duplicate_symptom_rows:
        flags.append("duplicate_symptom_text")
    if duplicate_sample_ids:
        flags.append("duplicate_sample_id")
    if groups_with_more_than_three:
        flags.append("more_than_two_variants_per_parent")

    class_summary = pd.crosstab(augmented["disease"], augmented["source_type"]).reset_index()
    class_summary["total"] = class_summary.drop(columns=["disease"]).sum(axis=1)
    class_summary["generated_percentage"] = (class_summary.get("controlled_synonym_augmentation", 0) / class_summary["total"] * 100).round(2)
    class_summary = class_summary.sort_values("disease")
    if args.class_csv:
        class_csv = Path(args.class_csv).expanduser().resolve()
        class_csv.parent.mkdir(parents=True, exist_ok=True)
        class_summary.to_csv(class_csv, index=False)

    report = [
        "# Augmentation Quality and Distribution Report",
        "",
        f"**Original input:** `{original_path}`  ",
        f"**Augmented input:** `{augmented_path}`  ",
        "**Purpose:** Verify deterministic controlled synonym augmentation; no clinical validation is performed.",
        "",
        "## 1. Summary",
        "",
        f"- Original metadata rows: **{len(original)}**",
        f"- Retained original rows: **{len(retained)}**",
        f"- Generated rows: **{len(generated)}**",
        f"- Expanded total: **{len(augmented)}**",
        f"- Disease classes: **{augmented.disease.nunique()}**",
        f"- Exact duplicate symptom texts: **{duplicate_symptom_rows}**",
        f"- Duplicate sample IDs: **{duplicate_sample_ids}**",
        f"- Maximum rows per base sample group: **{max_group_size}**",
        "",
        "## 2. Automated checks",
        "",
        "| Check | Result |",
        "|---|---|",
    ]
    for name, passed in checks.items():
        report.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    report += [
        f"| generated_text_unchanged | {'PASS' if unchanged_generated == 0 else 'FAIL'} ({unchanged_generated}) |",
        f"| generated_parent_class_mismatch | {'PASS' if wrong_parent_class == 0 else 'FAIL'} ({wrong_parent_class}) |",
        f"| duplicate_symptom_text | {'PASS' if duplicate_symptom_rows == 0 else 'FAIL'} ({duplicate_symptom_rows}) |",
        f"| duplicate_sample_id | {'PASS' if duplicate_sample_ids == 0 else 'FAIL'} ({duplicate_sample_ids}) |",
        "",
        "## 3. Source and language distribution",
        "",
        "| Category | Count | Percentage |",
        "|---|---:|---:|",
    ]
    for col in ["source_type", "language", "review_status"]:
        counts = augmented[col].value_counts()
        for value, count in counts.items():
            report.append(f"| {col}={value} | {int(count)} | {count / len(augmented) * 100:.2f}% |")
    report += [
        "",
        "## 4. Disease distribution",
        "",
        "| Disease | Original | Generated | Total | Generated % |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, row in class_summary.iterrows():
        original_count = int(row.get("fyp_original", 0))
        generated_count = int(row.get("controlled_synonym_augmentation", 0))
        report.append(f"| {row['disease']} | {original_count} | {generated_count} | {int(row['total'])} | {float(row['generated_percentage']):.2f}% |")

    low_generated = class_summary[class_summary.get("controlled_synonym_augmentation", 0) == 0]["disease"].tolist()
    report += [
        "",
        "## 5. Interpretation and warnings",
        "",
        "- Generated records are English-only because the synonym dictionary is English; Urdu records were intentionally not auto-augmented.",
        "- Each generated record retains its `base_sample_id`; split train/validation/test by this group to prevent paraphrase leakage.",
        "- Every generated record is marked `pending_review` and must be manually checked before research training.",
    ]
    if low_generated:
        report.append(f"- Classes with no generated variants: **{', '.join(low_generated)}**. Add class-specific reviewed synonyms later rather than forcing generic substitutions.")
    if flags:
        report.append(f"- **Quality flags requiring attention:** {', '.join(flags)}")
    else:
        report.append("- **No automated quality flags were detected.**")
    report += [
        "",
        "## 6. Recommended next action",
        "",
        "1. Review the generated rows manually, especially medically sensitive or emergency symptoms.",
        "2. Keep the original 465 rows unchanged.",
        "3. Use `base_sample_id` for grouped splitting.",
        "4. Do not report the expanded total as independent patient cases; these are controlled paraphrases.",
        "5. Create Urdu, Roman Urdu, and mixed-language augmentation only with separately reviewed language resources.",
    ]
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"Quality report written to: {report_path}")
    print(f"Rows: original={len(original)}, generated={len(generated)}, total={len(augmented)}")
    print(f"Flags: {flags if flags else 'none'}")


if __name__ == "__main__":
    main()
