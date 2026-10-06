# Augmentation Quality and Distribution Report

**Original input:** `C:\Users\dmain\OneDrive\Desktop\F25PROJECT664B0-App code\Backend\data\dataset_v1_metadata.csv`  
**Augmented input:** `C:\Users\dmain\OneDrive\Desktop\F25PROJECT664B0-App code\Backend\data\dataset_v2_augmented.csv`  
**Purpose:** Verify deterministic controlled synonym augmentation; no clinical validation is performed.

## 1. Summary

- Original metadata rows: **465**
- Retained original rows: **465**
- Generated rows: **478**
- Expanded total: **943**
- Disease classes: **31**
- Exact duplicate symptom texts: **0**
- Duplicate sample IDs: **0**
- Maximum rows per base sample group: **3**

## 2. Automated checks

| Check | Result |
|---|---|
| original_rows_retained | PASS |
| original_sample_ids_retained | PASS |
| original_base_ids_retained | PASS |
| unique_sample_ids | PASS |
| nonempty_symptoms | PASS |
| same_class_count | PASS |
| generated_has_parent | PASS |
| generated_is_not_original_source | PASS |
| generated_review_pending | PASS |
| generated_keeps_language | PASS |
| generated_text_unchanged | PASS (0) |
| generated_parent_class_mismatch | PASS (0) |
| duplicate_symptom_text | PASS (0) |
| duplicate_sample_id | PASS (0) |

## 3. Source and language distribution

| Category | Count | Percentage |
|---|---:|---:|
| source_type=controlled_synonym_augmentation | 478 | 50.69% |
| source_type=fyp_original | 465 | 49.31% |
| language=English | 788 | 83.56% |
| language=Urdu-script | 155 | 16.44% |
| review_status=pending_review | 478 | 50.69% |
| review_status=original_unreviewed | 465 | 49.31% |

## 4. Disease distribution

| Disease | Original | Generated | Total | Generated % |
|---|---:|---:|---:|---:|
| Allergic Rhinitis | 15 | 20 | 35 | 57.14% |
| Anemia | 15 | 20 | 35 | 57.14% |
| Anxiety Disorder | 15 | 5 | 20 | 25.00% |
| Appendicitis | 15 | 20 | 35 | 57.14% |
| Arthritis | 15 | 5 | 20 | 25.00% |
| Asthma | 15 | 20 | 35 | 57.14% |
| Back Pain | 15 | 0 | 15 | 0.00% |
| Common Cold | 15 | 19 | 34 | 55.88% |
| Dengue Fever | 15 | 19 | 34 | 55.88% |
| Depression | 15 | 8 | 23 | 34.78% |
| Diabetes | 15 | 20 | 35 | 57.14% |
| Flu | 15 | 20 | 35 | 57.14% |
| Food Poisoning | 14 | 18 | 32 | 56.25% |
| Gastritis | 15 | 20 | 35 | 57.14% |
| Heart Attack | 15 | 19 | 34 | 55.88% |
| Hepatitis | 15 | 20 | 35 | 57.14% |
| Hypertension | 15 | 20 | 35 | 57.14% |
| Kidney Disease | 15 | 8 | 23 | 34.78% |
| Malaria | 15 | 20 | 35 | 57.14% |
| Meningitis | 15 | 20 | 35 | 57.14% |
| Migraine | 15 | 20 | 35 | 57.14% |
| Pediatric Fever | 15 | 13 | 28 | 46.43% |
| Pneumonia | 15 | 20 | 35 | 57.14% |
| Psoriasis | 15 | 2 | 17 | 11.76% |
| Shingles | 15 | 0 | 15 | 0.00% |
| Skin Allergy | 15 | 6 | 21 | 28.57% |
| Stroke | 15 | 18 | 33 | 54.55% |
| Tonsillitis | 15 | 20 | 35 | 57.14% |
| Tuberculosis | 15 | 20 | 35 | 57.14% |
| Typhoid | 16 | 22 | 38 | 57.89% |
| UTI | 15 | 16 | 31 | 51.61% |

## 5. Interpretation and warnings

- Generated records are English-only because the synonym dictionary is English; Urdu records were intentionally not auto-augmented.
- Each generated record retains its `base_sample_id`; split train/validation/test by this group to prevent paraphrase leakage.
- Every generated record is marked `pending_review` and must be manually checked before research training.
- Classes with no generated variants: **Back Pain, Shingles**. Add class-specific reviewed synonyms later rather than forcing generic substitutions.
- **No automated quality flags were detected.**

## 6. Recommended next action

1. Review the generated rows manually, especially medically sensitive or emergency symptoms.
2. Keep the original 465 rows unchanged.
3. Use `base_sample_id` for grouped splitting.
4. Do not report the expanded total as independent patient cases; these are controlled paraphrases.
5. Create Urdu, Roman Urdu, and mixed-language augmentation only with separately reviewed language resources.
