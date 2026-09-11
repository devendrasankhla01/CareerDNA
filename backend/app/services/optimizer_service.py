"""Minimum-Change Career Optimizer (flagship differentiator B).

Algorithm (documented in docs/methodology.md):
  1. Baseline: trusted feature vector -> model probability p0.
  2. Candidates: for each deficient actionable feature, realistic target
     steps (+15/+25/benchmark) with effort (weeks). No changes to fixed
     historical data (10th/12th/CGPA/backlogs are excluded by design).
  3. Every candidate is tested by RE-RUNNING the trained model on the
     modified vector (interactions are therefore model-consistent).
  4. Greedy search: repeatedly add the highest impact-per-effort action
     until the target is reached or a small budget is exhausted.
  5. Output: smallest high-impact action set + projected model output.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.ml.features import ACTIONABLE_FEATURES
from app.models import Prediction, Student
from app.services.analysis_service import categorize
from app.services.model_service import model_service
from app.services.profile_service import build_feature_vector

MAX_ACTIONS = 4
MIN_IMPACT = 0.002  # probability points considered meaningful


def _score_candidates(features: dict[str, float | None]) -> list[dict]:
    candidates = []
    for feat, meta in ACTIONABLE_FEATURES.items():
        cur = features.get(feat)
        target = meta["target"]
        if feat in ("verified_project_count", "verified_internship_count"):
            if (cur or 0) < target:
                weeks = 3 if feat == "verified_project_count" else 8
                candidates.append({
                    "code": f"{feat}_increase",
                    "feature": feat,
                    "current": cur or 0,
                    "target": target,
                    "weeks": weeks,
                    "difficulty": "High" if feat == "verified_internship_count" else "Medium",
                    "label": meta["label"],
                    "kind": "count",
                })
            continue
        if cur is None or cur >= target:
            continue
        # realistic steps: a modest improvement and the full benchmark target
        for step_target in {cur + 15, target}:
            t = min(step_target, target, 100.0)
            if t <= cur:
                continue
            delta = t - cur
            weeks = 1 if delta <= 12 else (2 if delta <= 25 else 3)
            candidates.append({
                "code": f"{feat}_{int(t)}",
                "feature": feat,
                "current": cur,
                "target": round(t, 0),
                "weeks": weeks,
                "difficulty": "Low" if delta <= 12 else ("Medium" if delta <= 25 else "High"),
                "label": meta["label"],
                "kind": "score",
            })
    # keep only the best candidate per feature (largest impact will be
    # resolved during search; avoid duplicate same-feature actions)
    by_feature: dict[str, list[dict]] = {}
    for c in candidates:
        by_feature.setdefault(c["feature"], []).append(c)
    return by_feature


def _apply_candidate(features: dict[str, float | None], c: dict) -> dict[str, float | None]:
    f = dict(features)
    if c["kind"] == "count":
        f[c["feature"]] = c["target"]
        if c["feature"] == "verified_project_count":
            f["project_complexity_score"] = max(f.get("project_complexity_score") or 0, 70)
    else:
        f[c["feature"]] = c["target"]
    return f


FEATURE_TO_SKILL = {
    "sql_score": "SQL", "dsa_score": "DSA", "programming_score": "PYTHON",
    "web_dev_score": "BACKEND", "git_score": "GIT", "cloud_score": "CLOUD",
    "aptitude_score": "APTITUDE", "logical_score": "LOGICAL", "coding_score": "CODING",
    "communication_score": "COMMUNICATION", "interview_score": "INTERVIEW",
    "presentation_score": "PRESENTATION",
}


def _career_delta(db: Session, student: Student, career_code: str, features: dict) -> float | None:
    """Career match delta for hypothetical feature changes (deterministic)."""
    from app.services.career_service import match_score_for

    if not career_code:
        return None
    overrides = {
        FEATURE_TO_SKILL[f]: v for f, v in features.items()
        if f in FEATURE_TO_SKILL and v is not None
    }
    cur = match_score_for(db, student, career_code)
    hypo = match_score_for(db, student, career_code, overrides)
    if cur is None or hypo is None:
        return None
    return round(hypo - cur, 0)


def optimize(db: Session, student: Student, target_type: str = "GENERAL_READINESS",
             career_code: str | None = None) -> dict:
    from app.services.profile_service import build_feature_vector as _bfv

    s = get_settings()
    if not model_service.available:
        return {"status": "model_unavailable"}

    features = _bfv(db, student)
    p0 = model_service.predict_proba(features)
    baseline_score = round(p0 * 100, 1)
    baseline_category = categorize(baseline_score)

    if target_type == "CAREER_TRACK":
        from app.services.career_service import latest_matches
        matches = latest_matches(db, student)
        career_code = career_code or (matches[0]["career_code"] if matches else None)
        target_value = s.career_target_match
        baseline_career = next((m["match_score"] for m in matches if m["career_code"] == career_code), None)
    else:
        career_code = student.target_career_code
        target_value = s.ready_target
        baseline_career = None

    result = {
        "status": "ok",
        "target_type": target_type,
        "career_code": career_code,
        "baseline_readiness": baseline_score,
        "baseline_category": baseline_category,
        "baseline_career_match": baseline_career,
        "target": target_value,
    }

    if target_type == "GENERAL_READINESS" and baseline_score >= s.ready_target:
        result.update({
            "target_reached": True,
            "actions": [],
            "projected_readiness": baseline_score,
            "estimated_duration": "0 weeks",
            "message": "You are already in the Ready category. Focus on deepening your target career alignment.",
        })
        return result

    by_feature = _score_candidates(features)
    if not by_feature and baseline_score < target_value:
        result.update({
            "target_reached": False, "actions": [], "projected_readiness": baseline_score,
            "estimated_duration": "0 weeks",
            "message": "No short-term actionable skill changes are identified for your current profile. "
                       "Complete additional verified assessments or practical experience to unlock improvement paths.",
        })
        return result

    # evaluate all candidates once
    evaluated = []
    for feat, cands in by_feature.items():
        for c in cands:
            new_f = _apply_candidate(features, c)
            p = model_service.predict_proba(new_f)
            impact = p - p0
            if impact < MIN_IMPACT:
                continue
            c = dict(c)
            c["impact"] = impact
            if career_code:
                c["career_delta"] = _career_delta(db, student, career_code, new_f)
            evaluated.append(c)
    if not evaluated:
        result.update({
            "target_reached": False, "actions": [], "projected_readiness": baseline_score,
            "estimated_duration": "0 weeks",
            "message": "The model does not project meaningful improvement from short-term skill changes on your "
                       "current profile. Focus on completing verified assessments first.",
        })
        return result

    # greedy: highest impact-per-effort first; re-evaluate combined vector each step
    xai_rank = _xai_ranking(db, student)
    selected: list[dict] = []
    current_f = dict(features)
    current_p = p0
    reached = False

    while len(selected) < MAX_ACTIONS and not reached:
        best, best_key = None, None
        for c in evaluated:
            if c["feature"] in {a["feature"] for a in selected}:
                continue  # one action per feature
            combo = _apply_candidate(current_f, c)
            p_combo = model_service.predict_proba(combo)
            marginal = p_combo - current_p
            if marginal < MIN_IMPACT:
                continue
            career_b = 0.0
            if career_code:
                cd = _career_delta(db, student, career_code, combo)
                career_b = (cd or 0) / 100
            # minimum-change objective: impact per unit of real effort
            # (value movement + calendar time), not per calendar time alone.
            value_move = abs(c["target"] - (c["current"] or 0))
            effort = value_move + 0.6 * c["weeks"]
            key = (marginal + 0.4 * career_b) / max(effort, 1.0)
            if best_key is None or key > best_key:
                best, best_key = (c, p_combo, marginal, career_b), key
        if best is None:
            break
        c, p_combo, marginal, career_b = best
        selected.append({
            "code": c["code"], "feature": c["feature"], "label": c["label"],
            "current_value": c["current"], "target_value": c["target"],
            "estimated_weeks": c["weeks"], "difficulty": c["difficulty"],
            "projected_readiness_after": round(p_combo * 100, 1),
            "marginal_impact_points": round(marginal * 100, 1),
            "career_delta": c.get("career_delta"),
            "priority": "High" if len(selected) == 0 else ("Medium" if len(selected) == 1 else "Medium"),
            "reason": _reason({"feature": c["feature"], "label": c["label"],
                                "current_value": c["current"], "target_value": c["target"]},
                               xai_rank, career_code),
        })
        current_f = _apply_candidate(current_f, c)
        current_p = p_combo
        if target_type == "GENERAL_READINESS" and current_p * 100 >= s.ready_target:
            reached = True
        if target_type == "CAREER_TRACK":
            proj_career = _career_delta(db, student, career_code, current_f)
            base = baseline_career or 0
            if base + (proj_career or 0) >= target_value:
                reached = True

    total_weeks = sum(a["estimated_weeks"] for a in selected)
    lo = max(1, round(total_weeks * 0.85)) if total_weeks else 0
    hi = max(lo, round(total_weeks * 1.15)) if total_weeks else 0
    projected = round(current_p * 100, 1)
    projected_career = None
    if career_code:
        cd = _career_delta(db, student, career_code, current_f)
        projected_career = round((baseline_career or 0) + (cd or 0), 0)

    result.update({
        "target_reached": reached,
        "actions": selected[:MAX_ACTIONS],
        "projected_readiness": projected,
        "projected_category": categorize(projected),
        "projected_career_match": projected_career,
        "estimated_duration": f"{lo} week" if lo == hi else f"{lo}-{hi} weeks",
        "total_weeks": total_weeks,
        "message": ("The projected path reaches your target." if reached else
                    "The target is not projected to be reachable through short-term skill changes alone; "
                    "these actions provide the strongest realistic improvement path."),
    })
    return result


def _xai_ranking(db: Session, student: Student) -> list[str]:
    from app.services.analysis_service import get_current_prediction
    pred = get_current_prediction(db, student)
    if not pred or not pred.xai_json:
        return []
    lim = pred.xai_json.get("limiting", [])
    return [f["feature"] for f in lim]


def _reason(action: dict, xai_rank: list[str], career_code: str | None) -> str:
    label = action["label"]
    parts = []
    if action["feature"] in xai_rank:
        parts.append("This factor is currently limiting your model-estimated readiness")
    else:
        parts.append("This is a high-impact competency for your profile")
    if career_code:
        parts.append(" and a priority gap for your target career")
    parts.append(f". Projected model effect from {int(action['current_value'])} to {int(action['target_value'])}.")
    return " ".join(parts)


# ---------------------------------------------------------------- what-if
def simulate(db: Session, student: Student, changes: list[dict]) -> dict:
    """Controlled what-if simulation. Hypothetical only — never persisted."""
    if not model_service.available:
        return {"status": "model_unavailable"}
    base = build_feature_vector(db, student)
    p0 = model_service.predict_proba(base)
    new_f = dict(base)
    applied = []
    for ch in changes:
        feat = ch.get("feature")
        if feat not in ACTIONABLE_FEATURES:
            raise ValueError(f"Feature {feat} cannot be simulated")
        val = ch.get("value")
        if val is None:
            continue
        val = float(val)
        meta = ACTIONABLE_FEATURES[feat]
        if feat.endswith("_count"):
            if not (0 <= val <= 4):
                raise ValueError("Count out of range")
        else:
            if not (0 <= val <= 100):
                raise ValueError("Score out of range 0-100")
        new_f[feat] = val
        applied.append({"feature": feat, "from": base.get(feat), "to": round(val, 0)})
        if feat == "verified_project_count" and val > (base.get(feat) or 0):
            new_f["project_complexity_score"] = max(base.get("project_complexity_score") or 0, 70)
    p1 = model_service.predict_proba(new_f)
    out = {
        "status": "ok",
        "baseline_readiness": round(p0 * 100, 1),
        "projected_readiness": round(p1 * 100, 1),
        "delta_points": round((p1 - p0) * 100, 1),
        "applied": applied,
    }
    career_code = student.target_career_code
    if career_code and applied:
        cd = _career_delta(db, student, career_code, new_f)
        if cd is not None:
            from app.services.career_service import latest_matches
            m = next((x for x in latest_matches(db, student) if x["career_code"] == career_code), None)
            if m:
                out["career"] = {"career_code": career_code, "baseline": m["match_score"],
                                 "projected": round(m["match_score"] + cd, 0), "delta": cd}
    return out
