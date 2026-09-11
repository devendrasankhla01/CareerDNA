# Methodology

How the data, scores, explanations, and optimisers are actually computed. No number in the UI
is fabricated — each traces to a formula or a trained model below.

## 1. Synthetic data generation

Deterministic (fixed seed) so a reset always reproduces the same institution.

- **Current students (~600)** across 5 branches × semesters, each with a latent profile.
- **Historical training rows (~4,000)** with a `placed` label.
- **Latent-factor model:** each student has hidden factors (e.g. technical aptitude, effort,
  communication skill). Observable skills are generated from these latents + Gaussian noise, so
  skills are *correlated* realistically (a strong coder tends to score decently on DSA).
- **Readiness target** is generated from a weighted combination of the true latents + noise,
  which is what makes a classifier learnable and gives the model real (non-trivial) metrics.
- Known demo students are hand-crafted to anchor the story: Aarav (Near-Ready, one PENDING
  project), Tanvi (Ready), Diya (Needs Training).

`datasets/` holds the two synthetic CSVs (institution master, historical training data) for
inspection.

## 2. Readiness analysis pipeline

Run on login / on profile change / on verification (idempotent):

1. **Eligibility** — a student is *eligible* for a primary prediction only if they have enough
   verified/known signal (academic + assessment). Under-evidenced students are not given a
   misleading score.
2. **Feature assembly** — 23 features from the **verified** profile. Self-reported claims that
   are still PENDING / REJECTED are **excluded** from the primary prediction (they may appear
   in the passport, just not in the score). Verified practical items (projects, internships,
   certs) contribute as counts + complexity.
3. **Prediction** — `model.predict_proba` on the stored feature snapshot; the score is
   `probability × 100`.
4. **Category** — from configurable bands: `<60` Needs Training, `60–79.9` Near-Ready,
   `≥80` Ready.
5. **XAI** — for a Logistic Regression, the signed, scaled contribution of each feature to the
   decision function is computed from the student's own snapshot → top "strengthening" and top
   "limiting" factors with friendly labels.
6. **Profile trust** — weighted coverage of evidence categories (academic, technical,
   practical, assessment, communication, activity); more verified evidence ⇒ higher trust.
7. **Storage** — the prediction row stores `model_version`, the full `feature_snapshot`, the
   score, category, trust, and XAI, so every displayed value is reproducible.

## 3. Profile Trust & Data Completeness

- **Data Completeness** = share of *required* signals present (0–100).
- **Profile Trust** = category-weighted share of *verified* evidence (weights in
  `config.trust_weights`). High trust ⇒ the score rests on institution-verified facts.

## 4. Career Match (not ML)

A transparent weighted benchmark engine per track (FULL_STACK, DATA_ANALYST). Each track
defines distinct skill benchmarks; the match score is the weighted coverage of that track's
benchmarks by the verified profile, and the gaps are the skills below benchmark. Setting a
target track changes the gaps, the optimizer, and the roadmap — **never** the base readiness
score (readiness is career-agnostic by design).

## 5. Minimum-Change Career Optimizer ("Path to Ready")

Goal: the *smallest* set of actionable improvements that raises readiness.

- Candidate pool = **actionable** features only (skills the student can work on — not CGPA,
  not 10th %, not verified counts they can't change directly).
- Greedy selection: repeatedly pick the actionable feature whose improvement yields the largest
  *actual* model delta (re-runs the real model on the hypothetical vector), add it, stop when
  the remaining gain is marginal.
- **What-if mode** re-runs the trained model on any hypothetical feature values the student
  explores. Projections are labelled "model-estimated" and **never persisted** to the profile.

## 6. Institutional Intervention Optimizer

Ranks interventions for the *cohort*, using real skill deficits:

1. For each active intervention, compute the **affected cohort** (students below benchmark on
   its primary skill) and its **share** of analyzed students.
2. **Severity** = mean deficit of the primary feature vs benchmark.
3. **Simulated delta** = batch-re-run the model on the cohort with an assumed improvement.
4. **Ranking score** = weighted blend of population share, severity, simulated readiness delta,
   career relevance, and delivery effort (weeks).
5. **Cohort impact simulation** re-runs the model and returns baseline → projected category
   distributions + movers, always with the disclaimer: *"model-based projection, not a
   guaranteed outcome."*

## 7. Skill deficits & heatmap

Per skill, per branch: `% of evaluated students below the skill benchmark` with sample size `n`
(cells with `n < 5` are suppressed to avoid small-sample noise). Benchmarks are per-skill
institutional targets.

## 8. Institutional CSV import

Two phases (validate → confirm) so nothing bad is written without review:

- **Required columns:** `usn`, `semester` (1–8), `cgpa` (0–10). Everything else is optional:
  `name`, `email` (derived as `{usn}@{INSTITUTION_EMAIL_DOMAIN}` when absent), `branch`,
  `tenth_percentage`, `twelfth_percentage`, `backlog_history_count`, skill scores 0–100
  (`python, java, javascript, c_cpp, sql, dsa, git, cloud, coding, aptitude, logical,
  communication, interview, presentation`), and booleans `open_source, hackathon, leadership`.
- **Upsert by USN:** unknown USNs create the student (user account, profile, academic
  record); known USNs update the institution-owned fields.
- **Trust policy:** institution-provided skill scores are stored as `source=INSTITUTION,
  status=VERIFIED` — they are trusted immediately by the readiness engine (same as the
  academic record, which is institution-owned by design). Students can later add
  self-reported projects/internships in the app, which then go through faculty verification.
- **Eligibility:** a student is scored on import only if they meet the minimum-data gate
  (academic record + coding, aptitude and communication signals + practical experience
  declared). Students missing those fields are created but shown as "insufficient data"
  until the rest is added.
- After the confirm step, every imported student is re-analysed immediately, so readiness
  numbers appear in TPO analytics without any further action.

## 9. Verification & provenance

Every claimable item (project, internship, certification, activity, open-source, skill claim)
carries a status (PENDING / VERIFIED / CORRECTION_REQUIRED / REJECTED) and a provenance label
(Institution / Assessment / Faculty-Verified). Faculty decisions are category-scoped and fully
audited. Verification changes the *verified feature snapshot* and triggers re-analysis — this
is the causal lever that moves a student's readiness.
