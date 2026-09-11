# Model Card — Placement Readiness

**Version:** `careerdna-v1.0` · **Type:** binary classifier (placement-ready vs not) ·
**Selected model:** Logistic Regression · **Features:** 23 · **Explanations:** linear coefficients

> Read this first: the model predicts **placement readiness** — a 0–100 signal for how
> placement-ready a *verified* profile looks. It is **not** a prediction of whether a student
> will be hired, and its explanations are **associations, not causes**.

## Intended use

- Score a student's verified profile into a readiness category:
  **Needs Training (< 60) · Near-Ready (60–79.9) · Ready (≥ 80)** — bands configurable centrally.
- Rank *actionable* improvement opportunities per student ("Path to Ready").
- Aggregate into institutional skill-deficit analytics and intervention prioritisation.

**Not for use as:** an hiring gate, an admission decision, or an individual causal diagnosis.

## Training data

| | |
|---|---|
| Source | Synthetic, deterministic generator (seed 42) — latent factors + noise |
| Rows | 4,000 historical records; 800 held-out test (20%) |
| Target | "Placed / not placed", base rate 66% |
| Excluded | Identifiers, demographics, branch used as a predictor |

## Evaluated candidates (held-out test split, n = 800)

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---|---|---|
| **Logistic Regression** *(selected)* | 78.6% | 80.6% | 89.0% | **84.6%** | **0.827** |
| Random Forest | 74.7% | 76.3% | 89.6% | 82.4% | 0.795 |

**Selection rule:** highest (F1 + ROC-AUC) on the held-out test split, with 5-fold
cross-validated F1 as a stability check (selected CV F1 = 0.837). Logistic Regression won and
is also the more interpretable model, which suits a student-facing explanation surface.

Confusion matrix (selected): TN 159 · FP 113 · FN 58 · TP 470. Recall is deliberately weighted
high — missing a student who is ready is costlier than over-rating readiness, and the
"Ready" band is the only one that implies no further institutional action.

## Features (23)

Grouped as shown on the model page:

- **Academic** — CGPA, 10th %, 12th %, backlog history
- **Technical** — programming, SQL, DSA, web dev, Git, cloud, coding
- **Practical** — verified projects, project complexity, verified internships, verified
  certifications, open-source activity
- **Aptitude** — aptitude, logical reasoning
- **Soft skills** — communication, interview performance, presentation
- **Activities** — hackathons, leadership

**Global importance** (relative, top 10): communication, 10th %, hackathons, backlog history,
programming, verified projects, aptitude, logical reasoning, open-source, project complexity.
The full ranked list is served by `GET /api/model/info` and rendered on the *About the Model*
page.

## Explanations (XAI)

Local explanations come from the model's own linear coefficients applied to the student's
stored feature snapshot, mapped to friendly labels ("Communication", "SQL Proficiency", …),
with an optional technical view. Each contribution is a *relative model effect*, explicitly
labelled as "not a causal guarantee." This is transparent by construction — no black-box
permutation loop runs per request.

## Limitations

- Trained on synthetic data calibrated to plausible institutional patterns; real deployments
  must retrain on the institution's own (consent-governed) data.
- Readiness is a *profile* signal: it reflects verified evidence, not unobserved ability.
  A low score means "the verified profile shows gaps," not "the student is not capable."
- Thresholds (60/80) and trust weights are product configuration, chosen for a coherent demo
  story, not statistically derived optima.
- Cohort simulations (intervention impact) are model-based projections under an assumed skill
  improvement — always displayed with that disclaimer.
