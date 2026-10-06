# Dataset Expansion: First Three Steps

## Files to place in the repository

Copy these files into the existing project:

```
Backend/
├── data/
│   ├── dataset_v1_fyp_original.csv
│   └── symptom_synonyms.json
├── tools/
│   └── prepare_dataset_metadata.py
└── docs/
    └── DATASET_EXPANSION_SETUP.md
```

Do not edit or overwrite `dataset_v1_fyp_original.csv` after committing it. It is the frozen baseline for the paper.

## Step 1: Freeze the original dataset

The file `dataset_v1_fyp_original.csv` is a byte-for-byte copy of the original FYP dataset.

Expected properties:

- 465 records

- Columns: `disease,symptoms`

- SHA-256: `ef4f487141e16cb7a8c311aad23c0baf3ef900505f0e61a7852cfca23b86d299`

## Step 2: Generate metadata

Open VS Code with the project root, then open the integrated terminal.

PowerShell on Windows:

```
cd Backend
python -m pip install pandas
python tools/prepare_dataset_metadata.py `
  --input data/dataset_v1_fyp_original.csv `
  --output data/dataset_v1_metadata.csv
```

The backtick character is PowerShell’s line-continuation character. You can also run it on one line:

```
python tools/prepare_dataset_metadata.py --input data/dataset_v1_fyp_original.csv --output data/dataset_v1_metadata.csv
```

Git Bash, macOS, or Linux:

```bash
cd Backend
python3 -m pip install pandas
python3 tools/prepare_dataset_metadata.py \
  --input data/dataset_v1_fyp_original.csv \
  --output data/dataset_v1_metadata.csv
```

The generated metadata file has these columns:

```
sample_id
base_sample_id
disease
symptoms
language
input_style
source_type
severity
red_flag
review_status
review_notes
```

At this stage, `severity` and `red_flag` are intentionally `pending_review`. Do not automatically infer them from the disease name.

## Step 3: Use the synonym dictionary

The controlled dictionary is stored at:

```
Backend/data/symptom_synonyms.json
```

It is only a reviewable vocabulary resource. It does not generate records by itself and must not be used to replace symptoms automatically without preserving the original text.

Every future augmented record should retain:

```
base_sample_id
source_type = synthetic_reviewed
review_status = pending_review
```

Do not use the dictionary to alter red-flag phrases such as chest pain, severe breathing difficulty, one-sided weakness, loss of consciousness, or severe bleeding without medical review.

## Verify the output

From the `Backend` directory:

```
python -c "import pandas as pd; d=pd.read_csv('data/dataset_v1_metadata.csv'); print(d.shape); print(d['language'].value_counts())"
```

Expected output:

```
(465, 11)
English        310
Urdu-script    155
```

## Recommended Git commit

```bash
git add Backend/data/dataset_v1_fyp_original.csv \
        Backend/data/dataset_v1_metadata.csv \
        Backend/data/symptom_synonyms.json \
        Backend/tools/prepare_dataset_metadata.py \
        Backend/docs/DATASET_EXPANSION_SETUP.md

git commit -m "Freeze FYP dataset and add augmentation metadata setup"
git push origin main
```