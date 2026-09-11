"""Career benchmark engine (transparent, deterministic).

Match formula (documented in docs/methodology.md):
  For each benchmark skill: fulfillment = min(score / target, 1.0)
  (unscored skills count 0 for that weight and reduce data_coverage).
  match = 100 * sum(weight_i * fulfillment_i) / sum(all weights)
  Mandatory penalty: if any mandatory skill is unscored or below 40% of its
  target, the match is capped at 75.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import CareerBenchmark, CareerMatch, CareerTrack, Student
from app.services.profile_service import COMPLEXITY_MAP, _skill_map, _trusted_score

PROJECT_EXP_CAP = 75  # mandatory-gap cap


def _student_score(db: Session, student: Student, skills_map: dict, code: str) -> float | None:
    if code == "PROJECT_EXP":
        verified = [p for p in student.projects if p.status == "VERIFIED"]
        if not verified:
            return 0.0
        return float(max(COMPLEXITY_MAP.get(p.verified_complexity or p.claimed_complexity or "", 40)
                         for p in verified))
    return _trusted_score(skills_map.get(code))


def _match_for(db: Session, student: Student, skills_map: dict, career_code: str,
               bench: list[CareerBenchmark]) -> dict:
    total_weight = sum(b.importance_weight for b in bench) or 1.0
    evaluated_weight = 0.0
    acc = 0.0
    comparisons = []
    mandatory_breach = False
    for b in bench:
        score = _student_score(db, student, skills_map, b.skill_code)
        if score is not None:
            evaluated_weight += b.importance_weight
        ful = min(score / b.target_score, 1.0) if score is not None else 0.0
        acc += b.importance_weight * ful
        gap = (b.target_score - score) if score is not None else None
        if b.mandatory and (score is None or score < 0.4 * b.target_score):
            mandatory_breach = True
        comparisons.append({
            "skill_code": b.skill_code,
            "target": b.target_score,
            "current": None if score is None else round(score, 0),
            "gap": None if gap is None else round(gap, 0),
            "mandatory": b.mandatory,
            "weight": b.importance_weight,
        })
    match = 100 * acc / total_weight
    if mandatory_breach:
        match = min(match, PROJECT_EXP_CAP)
    match = round(min(max(match, 0.0), 100.0), 0)

    gaps = [c for c in comparisons if c["gap"] is not None and c["gap"] >= 10]
    gaps += [c for c in comparisons if c["gap"] is None and c["mandatory"]]
    major = len([g for g in gaps if g["gap"] is not None and g["gap"] >= 20]) + \
        len([g for g in gaps if g["gap"] is None and g["mandatory"]])

    return {
        "career_code": career_code,
        "match_score": match,
        "alignment": ("Strong" if match >= 80 else "Moderate" if match >= 65 else "Developing"),
        "data_coverage": round(evaluated_weight / total_weight * 100, 0),
        "major_gap_count": major,
        "comparisons": comparisons,
        "gaps": sorted(gaps, key=lambda g: ((g["gap"] if g["gap"] is not None else 100) * g["weight"]), reverse=True),
        "strengths": [c for c in comparisons if c["current"] is not None and c["current"] >= c["target"]][:4],
    }


def match_score_for(db: Session, student: Student, career_code: str,
                    overrides: dict[str, float | None] | None = None) -> float | None:
    """Deterministic match score; `overrides` may substitute hypothetical
    skill scores (used by the optimizer's career-delta evaluation)."""
    skills_map = _skill_map(db, student.id)
    bench = list(db.execute(
        select(CareerBenchmark).where(CareerBenchmark.career_code == career_code)).scalars())
    if not bench:
        return None
    total_w = sum(b.importance_weight for b in bench) or 1.0
    acc = 0.0
    breach = False
    for b in bench:
        score = overrides.get(b.skill_code) if overrides else None
        if score is None:
            score = _student_score(db, student, skills_map, b.skill_code)
        ful = min(score / b.target_score, 1.0) if score is not None else 0.0
        acc += b.importance_weight * ful
        if b.mandatory and (score is None or score < 0.4 * b.target_score):
            breach = True
    m = 100 * acc / total_w
    if breach:
        m = min(m, PROJECT_EXP_CAP)
    return round(min(max(m, 0.0), 100.0), 0)


def refresh_matches(db: Session, student: Student) -> None:
    skills_map = _skill_map(db, student.id)
    tracks = db.execute(select(CareerTrack).where(CareerTrack.active == True)).scalars().all()  # noqa: E712
    for old in db.execute(select(CareerMatch).where(
        CareerMatch.student_id == student.id, CareerMatch.is_current == True)).scalars():  # noqa: E712
        old.is_current = False
    for t in tracks:
        bench = db.execute(select(CareerBenchmark).where(CareerBenchmark.career_code == t.code)).scalars().all()
        if not bench:
            continue
        m = _match_for(db, student, skills_map, t.code, list(bench))
        db.add(CareerMatch(
            student_id=student.id, career_code=t.code, match_score=m["match_score"],
            major_gap_count=m["major_gap_count"], data_coverage=m["data_coverage"],
            is_current=True,
        ))
    db.flush()


def latest_matches(db: Session, student: Student) -> list[dict]:
    """Latest matches with track names; recomputes on demand if absent."""
    rows = db.execute(
        select(CareerMatch, CareerTrack)
        .join(CareerTrack, CareerMatch.career_code == CareerTrack.code)
        .where(CareerMatch.student_id == student.id, CareerMatch.is_current == True)  # noqa: E712
    ).all()
    if not rows:
        refresh_matches(db, student)
        db.commit()
        rows = db.execute(
            select(CareerMatch, CareerTrack)
            .join(CareerTrack, CareerMatch.career_code == CareerTrack.code)
            .where(CareerMatch.student_id == student.id, CareerMatch.is_current == True)  # noqa: E712
        ).all()
    out = [
        {
            "career_code": t.code, "name": t.name, "description": t.description,
            "match_score": m.match_score,
            "alignment": ("Strong" if m.match_score >= 80 else "Moderate" if m.match_score >= 65 else "Developing"),
            "major_gap_count": m.major_gap_count, "data_coverage": m.data_coverage,
        }
        for m, t in rows
    ]
    out.sort(key=lambda x: x["match_score"], reverse=True)
    return out


def career_detail(db: Session, student: Student, career_code: str | None) -> dict | None:
    skills_map = _skill_map(db, student.id)
    tracks = {t.code: t for t in db.execute(select(CareerTrack).where(CareerTrack.active == True)).scalars()}  # noqa: E712
    if career_code is None:
        matches = latest_matches(db, student)
        if not matches:
            return None
        career_code = matches[0]["career_code"]
    track = tracks.get(career_code)
    if not track:
        return None
    bench = db.execute(select(CareerBenchmark).where(CareerBenchmark.career_code == career_code)).scalars().all()
    return _match_for(db, student, skills_map, career_code, list(bench))


def set_target_career(db: Session, student: Student, career_code: str | None) -> None:
    if career_code is not None:
        track = db.execute(select(CareerTrack).where(CareerTrack.code == career_code)).scalars().first()
        if not track or not track.active:
            raise ValueError("Unknown career track")
    student.target_career_code = career_code
    db.commit()
