"""Institutional Intervention Optimizer (flagship differentiator C).

Pipeline:
  1. For each active intervention, find the affected cohort: students whose
     target skill is below benchmark (among analyzed, eligible profiles).
  2. Score priority:
       35% affected population share
       25% average gap severity
       25% simulated average readiness delta (model batch simulation)
       10% career relevance
        5% effort efficiency (inverse duration)
  3. Rank and expose; simulate() applies the assumed skill improvement to
     the cohort's stored feature snapshots, batch-runs the trained model,
     and returns before/after category distributions (projection only).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Intervention, Prediction, Skill, Student
from app.services.analysis_service import categorize
from app.services.model_service import model_service

SKILL_TO_FEATURE = {
    "SQL": "sql_score", "DSA": "dsa_score", "CODING": "coding_score",
    "PYTHON": "programming_score", "COMMUNICATION": "communication_score",
    "APTITUDE": "aptitude_score", "LOGICAL": "logical_score", "GIT": "git_score",
    "CLOUD": "cloud_score",
}


def _latest_predictions(db: Session) -> list[Prediction]:
    return db.execute(
        select(Prediction).join(Student, Prediction.student_id == Student.id)
        .where(Prediction.is_current == True, Student.is_active == True)  # noqa: E712
    ).scalars().all()


def _benchmark_for(db: Session, feature: str) -> float | None:
    skill = db.execute(select(Skill).where(Skill.code == feature.upper())).scalars().first()
    if skill and skill.general_benchmark:
        return float(skill.general_benchmark)
    mapping = {
        "coding_score": 70, "dsa_score": 65, "sql_score": 70,
        "programming_score": 70, "communication_score": 65, "aptitude_score": 70,
        "logical_score": 70, "git_score": 65, "cloud_score": 55,
    }
    return mapping.get(feature)


def _cohort_for_intervention(db: Session, preds: list[Prediction], iv: Intervention) -> list[Prediction]:
    cohort = []
    for p in preds:
        snap = p.feature_snapshot or {}
        for feature, mult in iv.feature_deltas.items():
            if feature.endswith("_count"):
                continue
            bench = _benchmark_for(db, feature)
            val = snap.get(feature)
            if bench is not None and val is not None and val < bench:
                cohort.append(p)
                break
    return cohort


def rank_interventions(db: Session, branch: str | None = None, semester: int | None = None) -> dict:
    s = get_settings()
    if not model_service.available:
        return {"status": "model_unavailable"}

    preds = _latest_predictions(db)
    if branch or semester:
        student_ids = {st.id for st in db.execute(select(Student).where(*_student_filter(branch, semester))).scalars()}
        preds = [p for p in preds if p.student_id in student_ids]

    analyzed = len(preds)
    if analyzed == 0:
        return {"status": "ok", "interventions": [], "analyzed_students": 0}

    raw = []
    for iv in db.execute(select(Intervention).where(Intervention.active == True)).scalars():  # noqa: E712
        cohort = _cohort_for_intervention(db, preds, iv)
        if len(cohort) < s.intervention_min_population:
            continue
        pop_share = len(cohort) / analyzed

        # severity: mean deficit of the primary feature vs benchmark
        primary_feature = next((f for f in iv.feature_deltas if not f.endswith("_count")), None)
        severity = 0.0
        if primary_feature:
            bench = _benchmark_for(db, primary_feature)
            vals = [(bench - (p.feature_snapshot or {}).get(primary_feature, bench))
                    for p in cohort
                    if (p.feature_snapshot or {}).get(primary_feature) is not None and bench]
            if vals and bench:
                severity = sum(vals) / len(vals) / bench

        # simulated delta at the default improvement
        sim = _simulate_cohort(db, cohort, iv.feature_deltas, s.intervention_default_improvement)
        avg_delta = sim["avg_readiness_delta"] / 100 if sim else 0.0

        score = (
            35 * pop_share
            + 25 * min(severity, 1.0)
            + 25 * min(avg_delta / 0.10, 1.0)  # 10 pts avg delta == max contribution
            + 10 * iv.career_relevance
            + 5 * max(0.0, (1 - iv.estimated_weeks / 6.0))
        )
        cohorts = _cohort_cohorts(db, cohort)
        raw.append({
            "intervention_id": iv.id,
            "code": iv.code,
            "name": iv.name,
            "skills": iv.skill_codes,
            "estimated_weeks": iv.estimated_weeks,
            "affected_students": len(cohort),
            "affected_share": round(pop_share, 3),
            "avg_severity": round(severity, 3),
            "avg_readiness_delta_at_default": round(sim["avg_readiness_delta"], 1) if sim else 0,
            "primary_cohorts": cohorts,
            "baseline_sim": sim,
            "score": round(score, 1),
            "priority": "High" if score >= 55 else ("Medium" if score >= 35 else "Low"),
            "reason_summary": _reason(iv, len(cohort), analyzed, cohorts, sim),
        })

    raw.sort(key=lambda r: r["score"], reverse=True)
    return {"status": "ok", "interventions": raw[:5], "analyzed_students": analyzed}


def _student_filter(branch: str | None, semester: int | None):
    conds = [Student.is_active == True]  # noqa: E712
    if branch:
        conds.append(Student.branch == branch)
    if semester:
        conds.append(Student.semester == semester)
    return conds


def _cohort_cohorts(db: Session, cohort: list[Prediction], top_n: int = 3) -> list[dict]:
    from collections import Counter
    c: Counter = Counter()
    for p in cohort:
        st = db.get(Student, p.student_id)
        if st:
            c[f"{st.branch} Sem {st.semester}"] += 1
    return [{"label": k, "count": v} for k, v in c.most_common(top_n)]


def _reason(iv: Intervention, affected: int, analyzed: int, cohorts: list[dict], sim: dict | None) -> str:
    top = cohorts[0]["label"] if cohorts else "multiple cohorts"
    delta = f" An average readiness gain of about {sim['avg_readiness_delta']} points is projected at the default improvement assumption." if sim else ""
    return (f"{affected} of {analyzed} analyzed students are below the benchmark for this skill "
            f"(most in {top}).{delta}")


def _simulate_cohort(db: Session, cohort: list[Prediction], feature_deltas: dict, improvement: float) -> dict | None:
    """Apply assumed improvement to the cohort's feature snapshots and
    batch-rerun the model. Pure projection — nothing is persisted."""
    if not model_service.available or not cohort:
        return None
    vectors = []
    for p in cohort:
        v = dict(p.feature_snapshot or {})
        for feature, mult in feature_deltas.items():
            if feature.endswith("_count"):
                v[feature] = min((v.get(feature) or 0) + mult, 4)
            else:
                cur = v.get(feature)
                if cur is None:
                    continue
                v[feature] = min(100.0, cur + improvement * mult)
        vectors.append(v)
    new_p = model_service.predict_proba_batch(vectors)
    base_counts, new_counts = {}, {}
    total_delta = 0.0
    movements: list[dict] = []
    moved = 0
    for p, np_ in zip(cohort, new_p):
        old_cat, new_cat = p.category, categorize(np_ * 100)
        base_counts[old_cat] = base_counts.get(old_cat, 0) + 1
        new_counts[new_cat] = new_counts.get(new_cat, 0) + 1
        total_delta += (np_ - p.probability) * 100
        if old_cat != new_cat:
            moved += 1
            movements.append({"from": old_cat, "to": new_cat})
    from collections import Counter
    movers = Counter((m["from"], m["to"]) for m in movements)
    n = len(cohort)
    return {
        "cohort_size": n,
        "avg_readiness_delta": round(total_delta / n, 1) if n else 0.0,
        "students_moving_category": moved,
        "movements": [
            {"from": f, "to": t, "count": c} for (f, t), c in movers.most_common()
        ],
        "baseline": {k: base_counts.get(k, 0) for k in ("READY", "NEAR_READY", "NEEDS_TRAINING")},
        "projected": {k: new_counts.get(k, 0) for k in ("READY", "NEAR_READY", "NEEDS_TRAINING")},
    }


def simulate(db: Session, intervention_code: str, improvement: float,
             branch: str | None = None, semester: int | None = None) -> dict:
    iv = db.execute(select(Intervention).where(Intervention.code == intervention_code)).scalars().first()
    if not iv:
        return {"status": "not_found"}
    if not (5 <= improvement <= 40):
        return {"status": "invalid_improvement", "message": "Assumed improvement must be between 5 and 40 points."}

    preds = _latest_predictions(db)
    if branch or semester:
        student_ids = {st.id for st in db.execute(select(Student).where(*_student_filter(branch, semester))).scalars()}
        preds = [p for p in preds if p.student_id in student_ids]
    cohort = _cohort_for_intervention(db, preds, iv)
    if not cohort:
        return {"status": "empty_cohort", "message": "No analyzed students below this skill benchmark in the selected cohort."}

    sim = _simulate_cohort(db, cohort, iv.feature_deltas, improvement)
    return {
        "status": "ok",
        "intervention": {"code": iv.code, "name": iv.name, "skills": iv.skill_codes,
                          "estimated_weeks": iv.estimated_weeks},
        "assumption": f"Average skill improvement +{improvement:.0f} points for participating students",
        "simulation": sim,
        "disclaimer": "Model-based projection based on assumed skill improvement. Actual outcomes may vary.",
    }


def cohort_students(db: Session, intervention_code: str, limit: int = 100) -> list[dict]:
    """Affected students for a ranked intervention (TPO drill-down)."""
    iv = db.execute(select(Intervention).where(Intervention.code == intervention_code)).scalars().first()
    if not iv:
        return []
    preds = _latest_predictions(db)
    cohort = _cohort_for_intervention(db, preds, iv)
    out = []
    for p in cohort:
        st = db.get(Student, p.student_id)
        if not st:
            continue
        xai = p.xai_json or {}
        top_limiting = xai.get("limiting", [{}])[0].get("label") if xai.get("limiting") else None
        out.append({
            "student_id": st.id, "name": st.user.display_name if st.user else st.usn,
            "usn": st.usn, "branch": st.branch, "semester": st.semester,
            "readiness": round(p.probability * 100, 1), "category": p.category,
            "profile_trust": p.profile_trust,
            "primary_gap": top_limiting,
        })
    out.sort(key=lambda r: r["readiness"])
    return out[:limit]
