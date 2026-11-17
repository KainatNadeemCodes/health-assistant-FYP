# AI-Powered Smart Health Assistant
**Group ID:** F25PROJECT664B0 | **Supervisor:** Mr. Shakeel Saeed  
**Course:** CS619 Final Year Project | Virtual University of Pakistan  
**Repository:** [https://github.com/KainatNadeemCodes/health-assistant-FYP](https://github.com/KainatNadeemCodes/health-assistant-FYP)

---

## Production-Grade Modernization Highlights

This project has been upgraded to a production-ready, clinical-grade architecture with zero-hallucination guardrails and modern enterprise DevOps:

1. **Security & Cryptography Hardening (Phase 1):**
   - Industry-standard **PBKDF2-HMAC-SHA256** password hashing with 100,000 iterations and salt, with backward-compatible automatic hash upgrading upon login.
   - **Signed JWT authentication** (`HS256`) with verified subject claims and Role-Based Access Control (RBAC).
   - Complete resolution of Insecure Direct Object References (IDOR) on consultation history endpoints.
   - Elimination of plaintext admin secrets in URL query strings; configurable strict CORS origins.

2. **Verified Clinical Dataset Expansion (Phase 2):**
   - Clinically grounded across **31 target disease classes** using verified monographs from **Columbia CUMC, CDC, WHO, and Mayo Clinic**.
   - Zero generative hallucinations: expanded from 465 rows to **4,029 balanced symptom-disease records** (~130 rows/disease across English & Urdu).
   - Retrained Logistic Regression + TF-IDF model achieving **98.26% Top-1 accuracy** and **99.75% Top-3 accuracy** with a Macro/Weighted F1-score of **0.9826**.

3. **Clinical Negation & Triage Guardrails (Phase 3):**
   - **Bilingual NegEx clinical negation engine** supporting both English (`no`, `denies`, `without`) and Urdu (`نہیں`, `کے بغیر`, `کوئی ... نہیں`) bounded by clause boundaries and contrastive conjunctions.
   - **False emergency triage escalation prevention**: patients denying red-flag symptoms (e.g. *"patient has mild headache but no chest pain"*) are safely protected from unwarranted emergency escalations.
   - **Out-of-Vocabulary (OOV) & low-confidence safety barriers**: ambiguous or gibberish inputs return safe physician consultation guidance instead of hallucinated diagnoses.

4. **Database & Architecture Modernization (Phase 4):**
   - **SQLAlchemy 2.0 dual-engine persistence layer** (`Backend/src/database.py`) providing zero-config local SQLite fallback with WAL mode alongside production **PostgreSQL** connection pooling (`DATABASE_URL`).
   - Declarative typed ORM schemas for `User`, `Consultation`, and `Feedback` with cascade foreign keys and CHECK constraints.
   - Database schema migrations managed via **Alembic** (`Backend/alembic/`).
   - **Asynchronous voice input pipeline**: CPU-intensive audio transcoding (pydub/ffmpeg) and speech decoding are offloaded to background worker threads via `asyncio.to_thread`, keeping FastAPI's event loop unblocked.
   - Cleaned dead Supabase boilerplate and added a global **React Error Boundary** (`Frontend/src/components/ErrorBoundary.tsx`) to eliminate white-screen crashes.

5. **DevOps, Containerization & CI/CD (Phase 5):**
   - **Multi-stage production Dockerfiles** for Backend (Python 3.11 slim, non-root user, ffmpeg) and Frontend (Node 20 build + lightweight Nginx runtime with SPA routing and Gzip compression).
   - **Docker Compose orchestration** (`docker-compose.yml`) linking PostgreSQL 16, FastAPI backend, and Nginx frontend with container health checks.
   - **GitHub Actions automated CI/CD pipeline** (`.github/workflows/ci.yml`) running backend automated tests, frontend builds, and Docker syntax checks on every pull request and push to `main`.

---

## Tech Stack

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Framer Motion, i18next (English + Urdu), Lucide React.
- **Backend:** FastAPI, Uvicorn, SQLAlchemy 2.0, Alembic, Pydantic, PyJWT.
- **Databases:** PostgreSQL 16 (production container) / SQLite with WAL mode (local development).
- **ML & NLP:** scikit-learn (Logistic Regression, TF-IDF Vectorization), NLTK, SHAP LinearExplainer.
- **Voice Pipeline:** Browser MediaRecorder API + Server-side asynchronous transcoding (pydub/ffmpeg) + Google Speech API.
- **Reporting:** fpdf2, ReportLab.
- **DevOps:** Docker (multi-stage), Docker Compose, Nginx, GitHub Actions CI/CD.

---

## Quick Start with Docker Compose (Recommended)

The entire production stack (PostgreSQL + FastAPI + Nginx Frontend) can be launched with a single command:

```bash
# Clone the repository
git clone https://github.com/KainatNadeemCodes/health-assistant-FYP.git
cd health-assistant-FYP

# Build and start all services
docker compose up --build
```

### Service Access:
- **Web Application:** [http://localhost](http://localhost) (or [http://localhost:8080](http://localhost:8080))
- **Backend API & Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **PostgreSQL Database:** `localhost:5432` (`db: health_assistant`, `user: health_user`)

---

## Manual Local Development Setup

### 1. Prerequisites
- **Python:** 3.11 or higher
- **Node.js:** 18 or higher (Node 20 recommended)
- **ffmpeg:** Required for voice input transcoding
  - Windows: `winget install ffmpeg` (or set `FFMPEG_PATH` environment variable)
  - Ubuntu/Debian: `sudo apt-get install ffmpeg`
  - macOS: `brew install ffmpeg`

### 2. Backend Setup
```bash
cd Backend

# Create and activate virtual environment
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations (or let init_db auto-initialize)
python -m alembic upgrade head

# Start FastAPI development server
uvicorn app:app --reload --port 8000
```
Backend runs at: [http://localhost:8000](http://localhost:8000) (Swagger UI: `/docs`).

### 3. Frontend Setup
```bash
cd Frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```
Frontend runs at: [http://localhost:5173](http://localhost:5173).

---

## Automated Test Suite

The project includes an automated test suite across security, clinical models, negation guardrails, and database persistence:

```bash
cd Backend
python -m unittest discover -s tests -p "test_*.py" -v
```

### Test Coverage Overview:
- `test_phase1.py`: Password hashing (PBKDF2), JWT token verification, IDOR prevention, admin RBAC.
- `test_phase2.py`: Dataset integrity (4,029 rows), English/Urdu prediction accuracy, triage alignment.
- `test_phase3.py`: Clinical negation (English & Urdu), false emergency prevention, OOV input protection.
- `test_phase4.py`: SQLAlchemy URL resolution (SQLite/PostgreSQL), ORM CRUD, admin analytics, async voice input, Alembic metadata.

**Result:** `22/22 tests passing` in < 4 seconds.

---

## Project Structure

```
health-assistant-FYP/
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI/CD pipeline
├── docker-compose.yml           # 3-tier container orchestration (Postgres, Backend, Frontend)
├── Backend/
│   ├── Dockerfile               # Multi-stage production container for FastAPI
│   ├── .dockerignore
│   ├── alembic.ini              # Alembic migration configuration
│   ├── alembic/                 # Version-controlled schema migrations
│   │   └── versions/
│   ├── app.py                   # FastAPI application entry point
│   ├── train_model.py           # ML training pipeline (Logistic Regression + TF-IDF)
│   ├── requirements.txt         # Production backend dependencies
│   ├── data/
│   │   ├── dataset.csv          # 4,029-row verified clinical training dataset
│   │   └── verified_clinical_kb.json # Grounded clinical monograph definitions
│   ├── models/
│   │   ├── model.pkl            # Trained Logistic Regression classifier
│   │   └── vectorizer.pkl       # Fitted bilingual TF-IDF vectorizer
│   ├── src/
│   │   ├── clinical_guardrails.py # Bilingual NegEx clinical negation engine
│   │   ├── database.py          # SQLAlchemy 2.0 dual-engine persistence layer
│   │   ├── security.py          # Salted PBKDF2 hashing & JWT authorization
│   │   ├── triage.py            # Layered triage engine with red-flag escalation
│   │   ├── preprocessing.py     # Bilingual text cleaning & validation
│   │   ├── feature_extraction.py# TF-IDF dense transformation
│   │   ├── classifier.py        # Top-k condition prediction
│   │   ├── explainability.py    # SHAP LinearExplainer + coefficient fallback
│   │   ├── pdf_generator.py     # Clinical consultation PDF generator
│   │   └── voice_processor.py   # Microphone capture & voice processing
│   └── tests/                   # 22 automated unit and integration tests
├── Frontend/
│   ├── Dockerfile               # Multi-stage container (Node 20 build + Nginx runtime)
│   ├── .dockerignore
│   ├── nginx.conf               # Nginx server configuration (SPA routing + Gzip)
│   ├── package.json
│   ├── vite.config.ts
│   └── src/
│       ├── App.tsx              # Root component wrapped with ErrorBoundary
│       ├── components/
│       │   └── ErrorBoundary.tsx# Global React error boundary with retry UI
│       ├── pages/               # SymptomChecker, Explainability, Dashboard, Admin
│       ├── hooks/               # useAuth, useLanguage
│       └── services/            # api.ts (backend HTTP client)
└── README.md
```

---

## Clinical Disclaimer

This application was developed as part of a university Final Year Project (FYP) for academic and educational evaluation. While built using clinically grounded monographs (CUMC, CDC, WHO, Mayo Clinic) and calibrated safety guardrails, **it is not a certified medical device**. All outputs represent AI-generated guidance and must never substitute for evaluation by a licensed healthcare professional. Always seek the advice of a qualified physician with any questions regarding medical conditions.
