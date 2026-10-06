# Dataset Audit Report

**Input file:** `C:\Users\dmain\OneDrive\Desktop\F25PROJECT664B0-App code\Backend\data\dataset.csv`  
**Generated:** `2026-10-06T00:05:38.073795+00:00`  
**Purpose:** Descriptive audit only; no records were changed.

## 1. Executive summary

- Total records: **465**
- Disease classes: **31**
- Records per class: **14–16** (mean 15.0)
- Duplicate symptom rows after whitespace/case normalization: **0**
- Rows with quality flags: **0**

## 2. Language/script distribution

| Category | Records | Percentage |
|---|---:|---:|
| English | 310 | 66.67% |
| Urdu-script | 155 | 33.33% |

## 3. Class distribution

| Disease | Records | Percentage |
|---|---:|---:|
| Allergic Rhinitis | 15 | 3.23% |
| Anemia | 15 | 3.23% |
| Anxiety Disorder | 15 | 3.23% |
| Appendicitis | 15 | 3.23% |
| Arthritis | 15 | 3.23% |
| Asthma | 15 | 3.23% |
| Back Pain | 15 | 3.23% |
| Common Cold | 15 | 3.23% |
| Dengue Fever | 15 | 3.23% |
| Depression | 15 | 3.23% |
| Diabetes | 15 | 3.23% |
| Flu | 15 | 3.23% |
| Food Poisoning | 14 | 3.01% |
| Gastritis | 15 | 3.23% |
| Heart Attack | 15 | 3.23% |
| Hepatitis | 15 | 3.23% |
| Hypertension | 15 | 3.23% |
| Kidney Disease | 15 | 3.23% |
| Malaria | 15 | 3.23% |
| Meningitis | 15 | 3.23% |
| Migraine | 15 | 3.23% |
| Pediatric Fever | 15 | 3.23% |
| Pneumonia | 15 | 3.23% |
| Psoriasis | 15 | 3.23% |
| Shingles | 15 | 3.23% |
| Skin Allergy | 15 | 3.23% |
| Stroke | 15 | 3.23% |
| Tonsillitis | 15 | 3.23% |
| Tuberculosis | 15 | 3.23% |
| Typhoid | 16 | 3.44% |
| UTI | 15 | 3.23% |

## 4. Text-length statistics

| Measure | Characters | Words |
|---|---:|---:|
| Minimum | 26 | 5 |
| Maximum | 71 | 13 |
| Mean | 50.17 | 8.09 |
| Median | 50.00 | 8.00 |

## 5. Quality findings

- No configured quality flags were detected.

## 6. Most represented classes

| Disease | Records |
|---|---:|
| Typhoid | 16 |
| Anemia | 15 |
| Allergic Rhinitis | 15 |
| Appendicitis | 15 |
| Arthritis | 15 |
| Asthma | 15 |
| Anxiety Disorder | 15 |
| Common Cold | 15 |
| Dengue Fever | 15 |
| Depression | 15 |

## 7. Interpretation notes

- This report describes the supplied dataset; it does not establish clinical validity.
- Language categories are detected from Unicode/script characters and should be manually reviewed.
- A row containing Urdu script and Latin letters is classified as `Mixed`.
- Keep this audit output with the dataset version used for each experiment.
- Review `quality_flags.csv` and `repeated_symptom_texts.csv` before expanding or splitting the dataset.

## Generated files

- `dataset_audit_report.md`
- `dataset_statistics.json`
- `class_distribution.csv`
- `language_distribution.csv`
- `class_language_distribution.csv`
- `quality_flags.csv`
- `repeated_symptom_texts.csv`
- `class_distribution.png`
- `language_distribution.png`
