# AI-Powered Smart Health Assistant
**Group ID:** F25PROJECT664B0 | **Supervisor:** Mr. Shakeel Saeed
**Course:** CS619 Final Year Project | Virtual University of Pakistan

---

## Note to Supervisor

This README reflects the **final submitted state of the application code**, which includes several refinements made after the report and SRS documentation were completed. These changes were driven by real implementation challenges discovered during development and testing. Each deviation from the original documentation is explained clearly below so there is no ambiguity between what the report describes and what the code actually does. The core scope, all functional requirements, and all use cases remain fully implemented as specified.

---

## What the System Does

**Bilingual Symptom Checker:** Users describe their symptoms in English or Urdu through a natural chat interface and receive AI-generated health guidance.

**Voice Input:** The browser records audio locally using the MediaRecorder API and sends it to the backend for server-side transcription. This approach was adopted after browser-native speech recognition proved unreliable on local networks (explained further below under Implementation Notes).

**Smart Triage:** Every result is classified into one of three levels — Self-Care, Visit GP, or Urgent Care. The engine uses a layered approach: red-flag emergency keywords are checked first and always take priority, followed by the clinical baseline for the predicted condition, followed by severity escalation keywords such as "severe" or "difficulty breathing." Patient metadata (age, sex, severity rating, chronic conditions, pregnancy status) further personalises the recommendation.

**Explainable AI:** The result screen shows which keywords from the user's input most influenced the prediction. The explainability module uses SHAP (SHapley Additive exPlanations) LinearExplainer as the primary method, with a coefficient-based fallback if SHAP is unavailable. This is described in detail under Implementation Notes.

**Patient Dashboard:** Registered users can view their last ten consultations, stored in a local SQLite database.

**PDF Reports:** A formatted health report can be downloaded from the Explainability page. This works for both guest and registered users because the full result payload is sent directly to the PDF endpoint rather than looked up from the database.

**Admin Panel:** A password-protected analytics dashboard showing triage distribution, top predicted conditions, specialist demand, daily activity trends, and average user feedback ratings. Supports user role management.

---

## Tech Stack

**Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Framer Motion, i18next (English + Urdu), Lucide React

**Backend:** FastAPI, Uvicorn, Pydantic, SQLite

**ML / NLP:** scikit-learn (Logistic Regression, TF-IDF Vectorization), NLTK, SHAP

**Voice:** MediaRecorder API (browser-side recording) + SpeechRecognition + pydub (server-side transcription via Google Speech API)

**PDF:** fpdf2, ReportLab

---

## Implementation Notes : Deviations from Submitted Documentation

The following points document where the final implementation differs from or extends what was described in the SRS and final report. These changes all represent improvements made during the implementation and testing phases.

### 1. Machine Learning Model : Logistic Regression (not Random Forest / Naive Bayes)

The SRS and some sections of the report reference Random Forest and Multinomial Naive Bayes as candidate models. The final trained model is **Logistic Regression** (`sklearn.linear_model.LogisticRegression`), selected because it performs better with TF-IDF sparse vectors and is directly compatible with SHAP's LinearExplainer. The `train_model.py` script documents this decision in full. The model is trained with `class_weight='balanced'` and stratified train/test split, and achieves the ≥80% Top-3 accuracy target specified in the SRS.

### 2. Explainability : SHAP LinearExplainer Added (UC-04 / FR13)

The original implementation used a coefficient × activation scoring method. The final version upgrades this to **SHAP LinearExplainer** as the primary explainability strategy, with the original coefficient method retained as an automatic fallback.

How the fallback works: if the `shap` library is not installed, the `ImportError` is caught silently and the system uses coefficient-based scoring instead. If SHAP throws any runtime error, the same fallback activates. The user always sees keyword explanations — there is no failure state visible on the frontend.

**Important setup note:** SHAP must be installed for the primary method to run. It is listed in `requirements.txt` as `shap>=0.44.0`. Running `pip install -r requirements.txt` will install it. To verify: `pip show shap`.

### 3. Voice Input : MediaRecorder API (not Web Speech API)

The report's module description for `SymptomChecker.tsx` mentions the Web Speech API. During testing, `webkitSpeechRecognition` was found to silently fail on the target network environment because Chrome sends audio directly to Google's servers from the browser, and those requests were unreachable.

The solution adopted was to remove the browser-native speech API entirely and replace it with:
- **Browser side:** MediaRecorder captures audio locally as a WebM/OGG blob with no external dependency.
- **Server side:** The blob is posted to `/voice-input`, converted to WAV using pydub + ffmpeg, and transcribed via Google Speech API from the server, which does not have the same network restriction.

This change is fully documented in the `SymptomChecker.tsx` file header and in the Challenges section of the report (Section 3.5). The functional outcome for the user — speaking symptoms and receiving a transcript — is identical to what the SRS specifies in UC-02.

### 4. Urdu Support : Active Improvement (not a pending future item)

The report's Challenges table describes Urdu misclassification as a known limitation with future support planned. In practice, active improvements were made before final submission:

- `preprocessing.py` was updated to version 3.0. Urdu input now bypasses English medical keyword validation entirely, since applying English-language filters to Urdu text was itself causing incorrect rejections.
- The training dataset was expanded from approximately 150 rows to **465 rows across 31 disease classes**, with Urdu symptom descriptions added so the TF-IDF vectorizer has actual Urdu vocabulary to match against.
- The TF-IDF vectorizer's token pattern was updated to explicitly include the Urdu Unicode range (`\u0600–\u06FF`).

Confidence scores for Urdu input remain lower than English on average, which is documented honestly in the limitations section. But the system no longer incorrectly rejects valid Urdu input.

### 5. ffmpeg Path : Requires Manual Update

To ensure the application is portable across different machines, app.py includes a detection script. It automatically detects if ffmpeg is installed in the system environment. If not found, it attempts to use a local fallback directory.

Troubleshooting: If the backend console shows a "FFmpeg not found" warning, the voice-input module will be disabled. To resolve this, install FFmpeg via winget install ffmpeg or update the dev_ffmpeg_path variable in app.py.
### 6. Admin Credentials : Hardcoded for Demo

The admin password (`admin2025`) is hardcoded in `app.py` and included in this README for ease of evaluation. In a production deployment this would be replaced with an environment variable and a proper authentication mechanism. The limitation is noted here transparently.

---

## Dataset

**File:** `Backend/data/dataset.csv`
**Rows:** 465 symptom–disease pairs
**Classes:** 31 diseases
**Languages:** English and Urdu

The dataset was curated and expanded during the implementation phase to support bilingual classification. `train_model.py` loads this file, preprocesses it using the same `clean_text` function used at runtime (ensuring training/inference consistency), and saves the trained model and vectorizer to `Backend/models/`.

---

## Prerequisites

- Python 3.11 (scikit-learn has compatibility issues with 3.12 and newer)
- Node.js 18 or higher
- ffmpeg (required for voice input audio conversion)

**Installing ffmpeg on Windows:**

Download from https://github.com/BtbN/FFmpeg-Builds/releases, extract, and update the path in `app.py` line 28 to point to the `bin` folder of your extracted ffmpeg directory. Alternatively, install via winget:

```bash
winget install ffmpeg
```

If installed via winget, the system PATH is updated automatically and the hardcoded line in `app.py` can be ignored.

---

## Running the Project

### Backend

```bash
cd Backend
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app:app --reload
```

Backend runs at: http://127.0.0.1:8000

Swagger API docs (confirms everything is working): http://127.0.0.1:8000/docs

To retrain the model after any dataset changes:

```bash
python train_model.py
```

### Frontend

```bash
cd Frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:5173

---

## Project Structure

```
F25PROJECT664B0/
├── Backend/
│   ├── app.py                  # FastAPI entry point — all API routes
│   ├── train_model.py          # ML training pipeline (Logistic Regression + TF-IDF)
│   ├── requirements.txt        # Python dependencies including shap>=0.44.0
│   ├── health_assistant.db     # SQLite database (auto-created on first run)
│   ├── data/
│   │   └── dataset.csv         # 465-row bilingual dataset, 31 disease classes
│   ├── models/
│   │   ├── model.pkl           # Trained Logistic Regression model
│   │   └── vectorizer.pkl      # Fitted TF-IDF vectorizer
│   └── src/
│       ├── preprocessing.py    # v3.0 — text cleaning + bilingual validation
│       ├── feature_extraction.py  # TF-IDF transform, returns dense numpy array
│       ├── classifier.py       # Model loader and top-k prediction
│       ├── triage.py           # Layered triage engine with red-flag escalation
│       ├── explainability.py   # v2.0 — SHAP LinearExplainer + coefficient fallback
│       ├── database.py         # All SQLite operations (WAL mode enabled)
│       ├── pdf_generator.py    # PDF health report generation
│       └── voice_processor.py  # Server-side MediaRecorder blob → transcript
├── Frontend/
│   └── src/
│       ├── pages/              # SymptomChecker, Explainability, Dashboard, Auth, Admin
│       ├── components/         # Navbar, FeedbackWidget, TriageBadge, Disclaimer
│       ├── hooks/              # useAuth, useLanguage
│       ├── services/           # api.ts — all backend fetch calls
│       └── i18n/               # en.json and ur.json translation files
└── README.md
```

---

## SRS Module Traceability

| File | Responsibility | SRS Reference |
|---|---|---|
| `app.py` | All API endpoints and request routing | UC-01 to UC-08, UC-14 |
| `train_model.py` | ML model training (Logistic Regression + TF-IDF) | FR2, FR5 |
| `classifier.py` | Top-k condition prediction with confidence scores | FR2, FR5 |
| `triage.py` | Layered triage with red-flag detection and personalisation | FR3, FR4, FR17, FR18 |
| `preprocessing.py` | Text cleaning, medical validation, bilingual support | FR1, FR9 |
| `explainability.py` | SHAP-based XAI with coefficient fallback | FR6, UC-04 |
| `database.py` | Consultation history, user auth, feedback, analytics | FR13, FR14 |
| `pdf_generator.py` | Downloadable health report | UC-14 |
| `voice_processor.py` | Server-side speech-to-text (MediaRecorder → WAV → transcript) | UC-02, FR9 |
| `dataset.csv` | 465-row bilingual training data | FR2, FR9 |

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Health check — returns API version and group ID |
| POST | `/predict` | Submit symptoms, receive triage, conditions, and XAI keywords |
| POST | `/voice-input` | Upload audio blob, receive transcript |
| POST | `/auth/register` | Create patient account |
| POST | `/auth/login` | Login and receive user object |
| GET | `/history` | Fetch last 10 consultations for a registered user |
| POST | `/feedback` | Submit 1–5 star rating for a consultation |
| POST | `/generate-pdf` | Generate and download PDF health report |
| POST | `/admin/login` | Admin authentication |
| GET | `/admin/analytics` | Aggregated analytics for admin dashboard |
| GET | `/admin/users` | Anonymised user list for admin panel |
| POST | `/admin/users/{id}/role` | Update a user's role |

---

## Test Credentials

**Admin panel password:** `admin2025`

**Guest access:** No login required. Limited to 5 consultations per session (enforced client-side).

---

## Known Limitations

**Urdu confidence scores:** Urdu predictions generally return lower confidence than English ones. The training dataset has been expanded with Urdu rows and the preprocessing pipeline now handles Urdu correctly, but the dataset remains smaller in Urdu than English. This is documented honestly in Section 3.5 of the final report.

**Voice input requires server-side internet:** Transcription is handled via Google Speech API from the backend server. If the server has no internet connection during a demo, voice input will return an error. Typed symptom input works fully offline.

**ffmpeg path:** Must be configured correctly on each machine as described above.

**SQLite for demo:** The database is SQLite, suitable for the academic demo environment. Section 3.6 of the report notes migration to a production database as a future enhancement.

---

## Disclaimer

This application was built for academic purposes as part of the CS619 Final Year Project at the Virtual University of Pakistan. It is not a certified medical device. All outputs are AI-generated guidance only and must not replace the advice of a qualified medical professional. Always consult a doctor for actual health decisions.