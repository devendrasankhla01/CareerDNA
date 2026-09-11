"""Analysis orchestration: trusted profile -> prediction -> XAI -> career.

A prediction is recomputed when trusted profile state changes (verification
decisions, academic import updates, manual refresh). Unverified claims do
not change the trusted profile version and therefore do not recompute the
verified prediction.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ml.features import FEATURE_SCHEMA_VERSION
from app.models import CareerMatch, Prediction, Student
from app.services import career_service
from app.services.model_service import model_service
from app.services.profile_service import (
    build_feature_vector,
    calculate_completeness,
    calculate_trust,
    check_eligibility,
)


def categorize(score: float) -> str:
    s = get_settings()
    if score < s.needs_training_lt:
        return "NEEDS_TRAINING"
    if score < s.near_ready_lt:
        return "NEAR_READY"
    return "READY"


CATEGORY_LABELS = {
    "NEEDS_TRAINING": "Needs Training",
    "NEAR_READY": "Near-Ready",
    "READY": "Ready",
}


def get_current_prediction(db: Session, student: Student) -> Prediction | None:
    return db.execute(
        select(Prediction)
        .where(Prediction.student_id == student.id, Prediction.is_current == True)  # noqa: E712
        .order_by(Prediction.created_at.desc())
    ).scalars().first()


def run_analysis(db: Session, student: Student, reason: str = "manual") -> Prediction | None:
    """Run the full analysis for a student. Returns the new prediction (or
    None when the profile is not yet eligible / model unavailable)."""
    if not model_service.available:
        return None

    features = build_feature_vector(db, student)
    eligibility = check_eligibility(db, student, features)
    if not eligibility["eligible"]:
        return None

    trust = calculate_trust(db, student)
    completeness = calculate_completeness(db, student, features)

    proba = model_service.predict_proba(features)
    score = proba * 100
    try:
        xai = model_service.explain(features)
    except Exception:
        xai = {"positive": [], "limiting": [], "note": "explanation_unavailable"}

    # supersede previous current prediction
    for p in db.execute(
        select(Prediction).where(Prediction.student_id == student.id, Prediction.is_current == True)  # noqa: E712
    ).scalars():
        p.is_current = False

    pred = Prediction(
        student_id=student.id,
        model_version=model_service.version,
        feature_schema=FEATURE_SCHEMA_VERSION,
        probability=round(proba, 4),
        category=categorize(score),
        profile_trust=trust["score"],
        data_completeness=completeness["score"],
        feature_snapshot=features,
        xai_json={
            "positive": xai.get("positive", []),
            "limiting": xai.get("limiting", []),
            "baseline": xai.get("baseline"),
            "model_output": xai.get("model_output"),
        },
        is_current=True,
    )
    db.add(pred)
    db.flush()

    # refresh cached career matches (derived from the same trusted profile)
    career_service.refresh_matches(db, student)

    student.profile_version += 1
    db.commit()
    return pred


def analysis_payload(db: Session, student: Student) -> dict:
    """Full student analysis response (prediction + XAI + career + gaps)."""
    pred = get_current_prediction(db, student)
    features = build_feature_vector(db, student)
    trust = calculate_trust(db, student)
    completeness = calculate_completeness(db, student, features)
    eligibility = check_eligibility(db, student, features)

    if pred is None:
        return {
            "status": "insufficient" if not eligibility["eligible"] else ("model_unavailable"
                                                                          if not model_service.available else "none"),
            "eligibility": eligibility,
            "trust": trust,
            "completeness": completeness,
        }

    xai = pred.xai_json or {}
    career = career_service.latest_matches(db, student)
    best = career[0] if career else None
    target = student.target_career_code
    target_match = next((m for m in career if m["career_code"] == target), best)

    return {
        "status": "ok",
        "prediction": {
            "score": round(pred.probability * 100, 1),
            "category": pred.category,
            "category_label": CATEGORY_LABELS[pred.category],
            "model_version": pred.model_version,
            "profile_trust": pred.profile_trust,
            "data_completeness": pred.data_completeness,
            "created_at": pred.created_at.isoformat(),
            "feature_snapshot": pred.feature_snapshot,
        },
        "xai": {
            "positive": xai.get("positive", []),
            "limiting": xai.get("limiting", []),
            "baseline": xai.get("baseline"),
            "model_output": xai.get("model_output"),
        },
        "career": {
            "matches": career,
            "best": best,
            "target_code": target,
            "target_match": target_match,
            "details": career_service.career_detail(db, student, target_match["career_code"] if target_match else None) if target_match else None,
        },
        "trust": trust,
        "completeness": completeness,
        "eligibility": eligibility,
        "summary_sentence": _summary_sentence(xai, pred.category),
    }


def _summary_sentence(xai: dict, category: str) -> str:
    pos = [f["label"] for f in xai.get("positive", [])[:2]]
    lim = [f["label"] for f in xai.get("limiting", [])[:2]]
    parts = []
    if pos:
        parts.append("Your strongest contributors are " + " and ".join(pos) + ".")
    if lim:
        parts.append(" " + " and ".join(lim) + " are currently your highest-impact improvement opportunities.")
    if not parts:
        parts.append("Your verified profile is balanced across the assessed dimensions.")
    return "".join(parts)
