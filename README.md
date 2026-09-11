# CareerDNA — AI Placement Predictor

An institutional career-readiness & upskilling engine. A real, working full-stack app:
students see a model-estimated **Placement Readiness** score built only from *verified*
profile evidence, faculty verify that evidence, and the TPO (Training & Placement Officer)
gets institutional analytics with a model-based intervention optimizer.

**Everything runs locally and free.** No paid APIs, no external LLMs, no paid DB, no hosting.

The app ships with **no student data** — you import your own students as a CSV from the TPO
*Student Data Import* page (new USNs create the student accounts; institution-provided skill
scores count as verified). A full synthetic demo roster (600 students) is available on demand
with `reset_demo --with-demo`.

---

## Quickstart (verified)

Prerequisites: **Python 3.11+** (tested on 3.13) and **Node 20+**.

### 1. Start the backend (port 8000)

```bash
cd backend
python -m venv .venv
# Linux/macOS:
.venv/bin/pip install -r requirements.txt
# Windows:
# .venv\Scripts\pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The model is pre-trained and shipped in `backend/artifacts/` (you don't need to train).
The demo database is created + seeded automatically on first run if missing.

### 2. Start the frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** — the Vite dev server proxies `/api` to the backend, so the
browser only talks to one origin.

> **If the page is blank:** the backend on port 8000 must be running first (the login screen
> still appears without it, but sign-in will fail). Open the browser DevTools console for
> details — the app now shows a readable error panel instead of a blank screen on crashes.

### 3. Import your students, then sign in

The institution starts **empty**. As the TPO, go to **Student Data Import**, download the
template, fill it with your students, and upload it. A USN not in the system **creates** the
student (they then sign in with USN + OTP); institution-provided skill scores are trusted
immediately and every imported student is scored at once.

| Role | How |
|---|---|
| **TPO admin** | Tab *Faculty / TPO* → `meera.iyer@northfielddemo.edu` / `TPOAdmin123!` |
| **Faculty verifier** | Tab *Faculty / TPO* → `kavya.raghavan@northfielddemo.edu` / `FacultyDemo123!` |
| **Any imported student** | Their USN → demo OTP shown on screen: `246810` |

The fixed OTP is an **environment-gated demo fallback** (`DEMO_MODE=true` by default; set
`DEMO_MODE=false` to require real SMTP-delivered OTPs).

> Want the full synthetic demo instead of your own data?
> `cd backend && .venv/bin/python -m scripts.reset_demo --with-demo`
> (flagship student `3PM24CS500` / Aarav Mehta, plus Ready and Needs-Training examples).

---

## Useful commands

```bash
# Reset to an EMPTY institution (your imports only; safe while the API is running)
cd backend && .venv/bin/python -m scripts.reset_demo

# ...or reset to the full synthetic demo roster
cd backend && .venv/bin/python -m scripts.reset_demo --with-demo

# Unit + API + ML + authorization tests (53 tests)
cd backend && .venv/bin/python -m pytest tests -q

# Live end-to-end smoke test (55 checks; needs the API running, MUTATES the demo DB)
cd backend && .venv/bin/python -m tests.e2e_smoke

# Rebuild + production bundle of the frontend
cd frontend && npm run build
```

Root convenience wrappers (bash): `./run.sh` (API + frontend) and `./reset.sh`.

## Where things live

```
backend/
  app/                FastAPI app: api/ (routes), services/ (domain logic), ml/ (features),
                      models/ (SQLAlchemy), core/ (config, security)
  artifacts/          Trained model + metrics.json + feature metadata + demo accounts
  scripts/            seed_demo.py, reset_demo.py
  tests/              pytest suite + e2e_smoke.py
frontend/             Vite + React 18 + TypeScript + Tailwind
docs/                 architecture, model card, demo script, methodology, UI screenshots
datasets/             Synthetic CSVs (institution master, historical training data)
```

## Docs

- [Architecture](docs/architecture.md) — components, security, configuration
- [Model card](docs/model-card.md) — real metrics, features, selection, limitations
- [Demo script](docs/demo-script.md) — 10-minute walkthrough of all three roles
- [Methodology](docs/methodology.md) — data generation, readiness engine, optimizers

## Responsible-AI notice

CareerDNA predicts **placement readiness, not placement outcomes**. Scores are model-estimated
signals computed from a student's verified profile; explanations are associations, not
causation; all projections ("Path to Ready", intervention simulations) are labelled
model-based and are never guarantees.
