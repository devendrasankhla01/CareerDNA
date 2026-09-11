# Architecture

CareerDNA is a two-process local system: a FastAPI backend (the single source of truth)
and a React frontend (a thin client). Both run on the developer's machine.

```
                 ┌─────────────────────────────────────────────┐
                 │                 Browser                     │
                 │   React 18 + Vite + Tailwind (port 5173)    │
                 │   Bearer-token auth, React Query            │
                 └───────────────┬─────────────────────────────┘
                                 │  same-origin  /api/*  (Vite proxy in dev)
                 ┌───────────────▼─────────────────────────────┐
                 │            FastAPI (port 8000)              │
                 │  ┌─────────┐  ┌──────────┐  ┌───────────┐   │
                 │  │  auth   │  │ student  │  │ faculty   │   │
                 │  │ OTP+JWT │  │ readiness│  │ verify    │   │
                 │  └─────────  │ passport │  │ queue     │   │
                 │               │ optimizer│  └───────────┘   │
                 │               │ roadmap  │  ┌───────────┐   │
                 │               └──────────  │ TPO admin │   │
                 │                             │ analytics │   │
                 │                             │ import    │   │
                 │                             └─────┬─────┘   │
                 │                                   │         │
                 │        ┌──────────────────────────┴─────┐   │
                 │        │ Services (domain logic)         │   │
                 │        │ analysis · verification · career│   │
                 │        │ optimizer · intervention · import│  │
                 │        └──────────────────────────┬─────┘   │
                 │        ┌──────────────────────────┴─────┐   │
                 │        │ model_service (joblib artifact) │   │
                 │        │ batch predict_proba + XAI       │   │
                 │        └─────────────────────────────────┘   │
                 └───────────────┬─────────────────────────────┘
                                 │ SQLAlchemy 2.x
                 ┌───────────────▼─────────────┐   ┌──────────────────┐
                 │  SQLite  careerdna.db       │   │ storage/evidence │
                 │  (Postgres-compatible SQL)  │   │ PDF/PNG/JPG ≤5MB │
                 └─────────────────────────────┘   └──────────────────┘
```

## Components

### Backend (`backend/`)

- **`app/api/`** — route handlers only (auth, student, faculty, tpo, model info). No business
  logic; every handler delegates to a service. RBAC is enforced with dependencies
  (`require_staff`, `require_tpo`) — role checks never happen in the frontend.
- **`app/services/`** — domain logic:
  - `auth_service` — OTP challenges (hashed, 5 attempts, 5-min expiry, 45 s resend cooldown),
    JWT session issuance, staff login. `DEMO_MODE` gates the fixed demo OTP fallback.
  - `analysis_service` — assembles the 23-feature vector from the *verified* profile
    (unverified self-claims are excluded from the primary prediction), runs the model, stores
    the prediction with `model_version` + full feature snapshot + XAI, computes readiness
    category (configurable bands), profile trust and data completeness.
  - `verification_service` — category-scoped faculty queue, approve / correct / reject with
    a full `VerificationReview` audit trail; verifying an item bumps profile trust and marks
    the student for re-analysis.
  - `career_service` — transparent weighted benchmark engine (not ML) for the FULL_STACK and
    DATA_ANALYST tracks: per-track benchmarks, match score, gaps. "Set as target" affects gaps,
    the optimizer and the roadmap — never the base readiness score.
  - `optimizer_service` — Minimum-Change Career Optimizer ("Path to Ready"): picks a small set
    of *actionable* features whose improvement would raise readiness most; what-if mode
    re-runs the trained model on hypothetical feature values. Nothing is ever persisted to the
    profile.
  - `intervention_service` — ranks interventions from real cohort skill deficits, simulates
    cohort impact by batch-rerunning the model with an assumed improvement, and returns
    baseline → projected readiness distributions.
  - `import_service` — two-phase CSV import (validate → confirm). True USN upsert: a USN not
    in the student master **creates** the student (user account + profile + institutional
    email), known USNs are updated. Institution-provided skill columns become VERIFIED
    INSTITUTION skill rows (trusted immediately); every imported student is analysed at once.
    Per-row error report, ignored-column report, template download, full job audit.
  - `model_service` — loads the joblib artifact once; `predict_proba_batch` for cohort math;
    exposes `metrics.json` + `global_importance.json` for the model page.
- **`app/ml/features.py`** — the 23-feature order, friendly labels, and groups (single source
  of truth shared by training, analysis, and the model page).
- **`app/core/config.py`** — every tunable (readiness bands, trust weights, thresholds, OTP
  policy, demo mode) in one place, overridable via env vars.

### Frontend (`frontend/`)

- Vite + React 18 + TypeScript (strict) + Tailwind. TanStack Query for server state.
- `src/api/client.ts` — one fetch wrapper (Bearer token, JSON, 401 → clear session).
- `src/lib/auth.tsx` — auth context; session persisted in `localStorage`.
- Pages by role: student (Readiness, Passport, Career, Path to Ready), faculty
  (Queue, Queue detail), TPO (Overview, Skills, Interventions, Import) + shared Model page.
- Every number on screen comes from the API — nothing is hardcoded or recomputed client-side.

### Data

- **SQLite** (`backend/careerdna.db`) via SQLAlchemy 2.x ORM. The SQL is
  Postgres-compatible (no SQLite-isms in queries); switching means changing `DATABASE_URL`.
- **Evidence files** in `backend/storage/evidence/` (PDF/PNG/JPG, ≤ 5 MB each).
- **Model artifacts** in `backend/artifacts/`: `placement_readiness_model.joblib`,
  `metrics.json`, `global_importance.json`, `feature_metadata.json`, `demo_accounts.json`.

## Security model

- **Roles**: `STUDENT`, `FACULTY`, `TPO_ADMIN`. Backend-enforced on every route.
  Faculty are additionally **category-scoped** (a TECHNICAL_SKILL verifier can never see the
  PROJECT queue). Students can never edit institutional fields (academic records are written
  only by the TPO import path). No self-registration for any role.
- **Auth**: students use USN → OTP to the institutional registered email (SMTP adapter is
  optional; without SMTP and with `DEMO_MODE=true`, the fixed demo OTP is shown on screen).
  Staff use email/password (bcrypt-hashed). Sessions are short-lived JWTs (12 h max).
- **Integrity**: readiness predictions are stored with a feature snapshot + model version;
  verification decisions are immutable audit rows; import jobs are fully audited.

## Key configuration (env vars)

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `sqlite:///backend/careerdna.db` | DB connection |
| `DEMO_MODE` | `true` | Allow the fixed demo OTP fallback |
| `DEMO_OTP` | `246810` | The demo OTP shown on screen |
| `SMTP_HOST/PORT/USER/PASSWORD/SENDER` | — | Real OTP delivery (optional) |
| `THRESHOLD_NEEDS_TRAINING_LT` | `60` | Readiness band boundary |
| `THRESHOLD_NEAR_READY_LT` | `80` | Readiness band boundary |
| `THRESHOLD_VULNERABLE_LT` | `60` | TPO "vulnerable" threshold |
| `INTERVENTION_MIN_POPULATION` | `15` | Min cohort size for an intervention to rank |
| `INTERVENTION_DEFAULT_IMPROVEMENT` | `15` | Assumed skill gain used in default ranking |
| `MAX_UPLOAD_MB` | `5` | Evidence/import upload limit |
