#!/usr/bin/env python3
"""
Audit the Smart Health Assistant symptom dataset.

Usage:
    python dataset_audit.py \
        --input Backend/data/dataset.csv \
        --output audit_reports

The script creates:
    dataset_audit_report.md
    dataset_statistics.json
    class_distribution.csv
    language_distribution.csv
    class_language_distribution.csv
    quality_flags.csv
    class_distribution.png (when matplotlib is installed)
    language_distribution.png (when matplotlib is installed)

Expected input columns:
    disease,symptoms

No records are changed by this script. It only reads the dataset and writes
statistics/reports to the selected output directory.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

URDU_RE = re.compile(r"[\u0600-\u06FF]")
LATIN_RE = re.compile(r"[A-Za-z]")
WHITESPACE_RE = re.compile(r"\s+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit a symptom classification dataset.")
    parser.add_argument("--input", required=True, help="Path to dataset CSV")
    parser.add_argument(
        "--output",
        default="audit_reports",
        help="Directory where reports will be written (default: audit_reports)",
    )
    parser.add_argument(
        "--short-threshold",
        type=int,
        default=5,
        help="Flag symptom text shorter than this many characters (default: 5)",
    )
    return parser.parse_args()


def json_safe(value: Any) -> Any:
    """Convert pandas/numpy scalar values into JSON-safe Python values."""
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def normalize_text(text: str) -> str:
    text = str(text).casefold().strip()
    return WHITESPACE_RE.sub(" ", text)


def classify_language(text: str) -> str:
    """Classify rows as English, Urdu-script, Mixed, or Other."""
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


def pct(part: int, whole: int) -> float:
    return round((part / whole * 100) if whole else 0.0, 2)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def create_charts(output_dir: Path, class_counts: pd.Series, language_counts: pd.Series) -> list[str]:
    """Create simple charts if matplotlib is installed; otherwise continue safely."""
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    created = []
    plt.figure(figsize=(11, 8))
    class_counts.sort_values().plot(kind="barh", color="#2563eb")
    plt.title("Dataset Records by Disease Class")
    plt.xlabel("Number of records")
    plt.ylabel("Disease")
    plt.tight_layout()
    path = output_dir / "class_distribution.png"
    plt.savefig(path, dpi=180)
    plt.close()
    created.append(path.name)

    plt.figure(figsize=(7, 5))
    language_counts.plot(kind="bar", color=["#16a34a", "#7c3aed", "#ea580c", "#64748b"])
    plt.title("Dataset Records by Detected Language")
    plt.xlabel("Language category")
    plt.ylabel("Number of records")
    plt.xticks(rotation=0)
    plt.tight_layout()
    path = output_dir / "language_distribution.png"
    plt.savefig(path, dpi=180)
    plt.close()
    created.append(path.name)
    return created


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Dataset not found: {input_path}")

    df = pd.read_csv(input_path)
    df.columns = [str(column).strip() for column in df.columns]
    required = {"disease", "symptoms"}
    missing_columns = sorted(required - set(df.columns))
    if missing_columns:
        raise ValueError(
            f"Missing required columns: {missing_columns}. Found: {list(df.columns)}"
        )

    original_rows = len(df)
    null_counts = {column: int(value) for column, value in df.isna().sum().items()}
    df["disease_clean"] = df["disease"].fillna("").astype(str).str.strip()
    df["symptoms_clean"] = df["symptoms"].fillna("").astype(str).str.strip()
    df["normalized_symptoms"] = df["symptoms_clean"].map(normalize_text)
    df["language_category"] = df["symptoms_clean"].map(classify_language)
    df["character_count"] = df["symptoms_clean"].str.len()
    df["word_count"] = df["symptoms_clean"].str.split().str.len()

    exact_duplicate_mask = df["normalized_symptoms"].duplicated(keep=False)
    disease_duplicate_mask = df.duplicated(subset=["disease_clean", "normalized_symptoms"], keep=False)
    quality_flags: list[dict[str, Any]] = []
    for index, row in df.iterrows():
        flags: list[str] = []
        if not row["disease_clean"]:
            flags.append("missing_disease")
        if not row["symptoms_clean"]:
            flags.append("missing_symptoms")
        if int(row["character_count"]) < args.short_threshold:
            flags.append("very_short_text")
        if bool(exact_duplicate_mask.loc[index]):
            flags.append("duplicate_symptoms")
        if bool(disease_duplicate_mask.loc[index]):
            flags.append("duplicate_disease_symptoms")
        if flags:
            quality_flags.append(
                {
                    "row_number": int(index) + 2,
                    "disease": row["disease_clean"],
                    "symptoms": row["symptoms_clean"],
                    "language": row["language_category"],
                    "character_count": int(row["character_count"]),
                    "word_count": int(row["word_count"]),
                    "flags": ";".join(flags),
                }
            )

    class_counts = df["disease_clean"].value_counts().sort_index()
    language_counts = df["language_category"].value_counts().sort_index()
    cross_tab = pd.crosstab(df["disease_clean"], df["language_category"]).sort_index()

    class_rows = [
        {
            "disease": str(disease),
            "records": int(count),
            "percentage": pct(int(count), original_rows),
        }
        for disease, count in class_counts.items()
    ]
    language_rows = [
        {
            "language": str(language),
            "records": int(count),
            "percentage": pct(int(count), original_rows),
        }
        for language, count in language_counts.items()
    ]
    cross_rows = []
    for disease, row in cross_tab.iterrows():
        item = {"disease": str(disease)}
        for language in cross_tab.columns:
            item[str(language)] = int(row[language])
        cross_rows.append(item)

    repeated_texts = []
    for normalized, count in df["normalized_symptoms"].value_counts().items():
        if count > 1:
            examples = df.loc[df["normalized_symptoms"] == normalized, "symptoms_clean"].tolist()
            repeated_texts.append(
                {
                    "normalized_symptoms": normalized,
                    "count": int(count),
                    "examples": " | ".join(examples[:5]),
                }
            )

    statistics = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_path),
        "row_count": original_rows,
        "column_names": list(df.columns[:2]),
        "null_counts": null_counts,
        "duplicate_symptom_rows": int(df["normalized_symptoms"].duplicated().sum()),
        "duplicate_disease_symptom_rows": int(df.duplicated(subset=["disease_clean", "normalized_symptoms"]).sum()),
        "unique_disease_classes": int(df["disease_clean"].nunique()),
        "class_min_records": int(class_counts.min()) if len(class_counts) else 0,
        "class_max_records": int(class_counts.max()) if len(class_counts) else 0,
        "class_mean_records": round(float(class_counts.mean()), 2) if len(class_counts) else 0.0,
        "language_distribution": {str(k): int(v) for k, v in language_counts.items()},
        "language_percentages": {str(k): pct(int(v), original_rows) for k, v in language_counts.items()},
        "symptom_character_count": {
            "min": int(df["character_count"].min()) if original_rows else 0,
            "max": int(df["character_count"].max()) if original_rows else 0,
            "mean": round(float(df["character_count"].mean()), 2) if original_rows else 0.0,
            "median": float(df["character_count"].median()) if original_rows else 0.0,
        },
        "symptom_word_count": {
            "min": int(df["word_count"].min()) if original_rows else 0,
            "max": int(df["word_count"].max()) if original_rows else 0,
            "mean": round(float(df["word_count"].mean()), 2) if original_rows else 0.0,
            "median": float(df["word_count"].median()) if original_rows else 0.0,
        },
        "quality_flagged_rows": len(quality_flags),
        "quality_flag_counts": dict(Counter(flag for row in quality_flags for flag in row["flags"].split(";"))),
    }

    write_csv(output_dir / "class_distribution.csv", class_rows)
    write_csv(output_dir / "language_distribution.csv", language_rows)
    write_csv(output_dir / "class_language_distribution.csv", cross_rows)
    write_csv(output_dir / "quality_flags.csv", quality_flags)
    write_csv(output_dir / "repeated_symptom_texts.csv", repeated_texts)

    chart_files = create_charts(output_dir, class_counts, language_counts)
    statistics["generated_chart_files"] = chart_files
    with (output_dir / "dataset_statistics.json").open("w", encoding="utf-8") as handle:
        json.dump(json_safe(statistics), handle, indent=2, ensure_ascii=False)

    top_classes = class_counts.sort_values(ascending=False).head(10)
    report_lines = [
        "# Dataset Audit Report",
        "",
        f"**Input file:** `{input_path}`  ",
        f"**Generated:** `{statistics['generated_at_utc']}`  ",
        "**Purpose:** Descriptive audit only; no records were changed.",
        "",
        "## 1. Executive summary",
        "",
        f"- Total records: **{original_rows}**",
        f"- Disease classes: **{statistics['unique_disease_classes']}**",
        f"- Records per class: **{statistics['class_min_records']}–{statistics['class_max_records']}** "
        f"(mean {statistics['class_mean_records']})",
        f"- Duplicate symptom rows after whitespace/case normalization: **{statistics['duplicate_symptom_rows']}**",
        f"- Rows with quality flags: **{statistics['quality_flagged_rows']}**",
        "",
        "## 2. Language/script distribution",
        "",
        "| Category | Records | Percentage |",
        "|---|---:|---:|",
    ]
    for row in language_rows:
        report_lines.append(f"| {row['language']} | {row['records']} | {row['percentage']:.2f}% |")

    report_lines += [
        "",
        "## 3. Class distribution",
        "",
        "| Disease | Records | Percentage |",
        "|---|---:|---:|",
    ]
    for row in class_rows:
        report_lines.append(f"| {row['disease']} | {row['records']} | {row['percentage']:.2f}% |")

    report_lines += [
        "",
        "## 4. Text-length statistics",
        "",
        "| Measure | Characters | Words |",
        "|---|---:|---:|",
        f"| Minimum | {statistics['symptom_character_count']['min']} | {statistics['symptom_word_count']['min']} |",
        f"| Maximum | {statistics['symptom_character_count']['max']} | {statistics['symptom_word_count']['max']} |",
        f"| Mean | {statistics['symptom_character_count']['mean']:.2f} | {statistics['symptom_word_count']['mean']:.2f} |",
        f"| Median | {statistics['symptom_character_count']['median']:.2f} | {statistics['symptom_word_count']['median']:.2f} |",
        "",
        "## 5. Quality findings",
        "",
    ]
    if quality_flags:
        for flag, count in statistics["quality_flag_counts"].items():
            report_lines.append(f"- `{flag}`: {count} row(s)")
    else:
        report_lines.append("- No configured quality flags were detected.")

    report_lines += [
        "",
        "## 6. Most represented classes",
        "",
        "| Disease | Records |",
        "|---|---:|",
    ]
    for disease, count in top_classes.items():
        report_lines.append(f"| {disease} | {int(count)} |")

    report_lines += [
        "",
        "## 7. Interpretation notes",
        "",
        "- This report describes the supplied dataset; it does not establish clinical validity.",
        "- Language categories are detected from Unicode/script characters and should be manually reviewed.",
        "- A row containing Urdu script and Latin letters is classified as `Mixed`.",
        "- Keep this audit output with the dataset version used for each experiment.",
        "- Review `quality_flags.csv` and `repeated_symptom_texts.csv` before expanding or splitting the dataset.",
        "",
        "## Generated files",
        "",
    ]
    generated_files = [
        "dataset_audit_report.md",
        "dataset_statistics.json",
        "class_distribution.csv",
        "language_distribution.csv",
        "class_language_distribution.csv",
        "quality_flags.csv",
        "repeated_symptom_texts.csv",
    ] + chart_files
    report_lines.extend(f"- `{name}`" for name in generated_files)
    (output_dir / "dataset_audit_report.md").write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"Audit complete: {input_path}")
    print(f"Reports written to: {output_dir}")
    print(f"Rows: {original_rows} | Classes: {statistics['unique_disease_classes']}")
    print(f"Languages/scripts: {statistics['language_distribution']}")
    print(f"Duplicate symptom rows: {statistics['duplicate_symptom_rows']}")
    print(f"Quality-flagged rows: {statistics['quality_flagged_rows']}")


if __name__ == "__main__":
    main()
