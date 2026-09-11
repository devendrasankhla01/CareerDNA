"""TPO institutional analytics (aggregation only — no per-row data leaks)."""
from __future__ import annotations

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    CareerMatch,
    CareerTrack,
    Prediction,
    Skill,
    Student,
    VerificationRequest,
)
from app.services.analysis_service import CATEGORY_LABELS, categorize

HEATMAP_SKILLS = ["SQL", "DSA", "CODING", "JAVASCRIPT", "PYTHON", "COMMUNICATION", "APTITUDE", "GIT"]
FEATURE_TO_SKILL_REV = {
    "sql_score": "SQL", "dsa_score": "DSA", "coding_score": "CODING",
    "web_dev_score": "JAVASCRIPT", "programming_score": "PYTHON",
    "communication_score": "COMMUNICATION", "aptitude_score": "APTITUDE",
    "git_score": "GIT",
}


def _base_query(db: Session, branch: str | None = None, semester: int | None = None,
                category: str | None = None, min_score: float | None = None,
                max_score: float | None = None):
    preds = (
        db.execute(
            select(Prediction).join(Student, Prediction.student_id == Student.id)
            .where(Prediction.is_current == True, Student.is_active == True)  # noqa: E712
        )
    ).scalars().all()
    out = []
    for p in preds:
        st = db.get(Student, p.student_id)
        if not st:
            continue
        if branch and st.branch != branch:
            continue
        if semester and st.semester != semester:
            continue
        score = p.probability * 100
        if category and p.category != category:
            continue
        if min_score is not None and score < min_score:
            continue
        if max_score is not None and score > max_score:
            continue
        out.append((st, p, score))
    return out


def _category_counts(pairs: list) -> dict:
    c = Counter(p.category for _, p, _ in pairs)
    return {k: c.get(k, 0) for k in ("READY", "NEAR_READY", "NEEDS_TRAINING")}


def overview(db: Session, branch: str | None = None, semester: int | None = None) -> dict:
    s = get_settings()
    all_students = db.execute(select(Student).where(Student.is_active == True)).scalars().all()  # noqa: E712
    pairs = _base_query(db, branch, semester)
    analyzed = len(pairs)
    total = len([st for st in all_students if (not branch or st.branch == branch)
                 and (not semester or st.semester == semester)])
    counts = _category_counts(pairs)
    avg = sum(sc for _, _, sc in pairs) / analyzed if analyzed else None

    # trust/verification coverage
    high = sum(1 for _, p, _ in pairs if p.profile_trust >= 75)
    partial = sum(1 for _, p, _ in pairs if 40 <= p.profile_trust < 75)
    low = analyzed - high - partial

    # branch-wise
    by_branch: dict[str, dict] = {}
    for st, p, sc in pairs:
        b = by_branch.setdefault(st.branch, {"students": 0, "sum": 0.0, "cats": Counter()})
        b["students"] += 1
        b["sum"] += sc
        b["cats"][p.category] += 1
    branch_metrics = []
    for br in sorted(by_branch):
        b = by_branch[br]
        n = b["students"]
        branch_metrics.append({
            "branch": br, "student_count": n,
            "average_readiness": round(b["sum"] / n, 1),
            "ready_percentage": round(b["cats"].get("READY", 0) / n * 100, 0),
            "near_ready_percentage": round(b["cats"].get("NEAR_READY", 0) / n * 100, 0),
            "needs_training_percentage": round(b["cats"].get("NEEDS_TRAINING", 0) / n * 100, 0),
        })
    branch_metrics.sort(key=lambda x: x["average_readiness"], reverse=True)

    deficits = skill_deficits(db, branch, semester)["deficits"][:5]
    vulnerable = sum(1 for _, p, sc in pairs if sc < s.vulnerable_lt)

    return {
        "status": "ok",
        "population": {"total_students": total, "analyzed_students": analyzed,
                       "not_analyzed": max(total - analyzed, 0)},
        "readiness": {
            "ready": counts["READY"], "near_ready": counts["NEAR_READY"],
            "needs_training": counts["NEEDS_TRAINING"],
            "ready_percentage": round(counts["READY"] / analyzed * 100, 1) if analyzed else None,
            "near_ready_percentage": round(counts["NEAR_READY"] / analyzed * 100, 1) if analyzed else None,
            "needs_training_percentage": round(counts["NEEDS_TRAINING"] / analyzed * 100, 1) if analyzed else None,
            "average_readiness": round(avg, 1) if avg is not None else None,
        },
        "quality": {"high_trust": high, "partial_trust": partial, "low_trust": low,
                    "coverage_note": "Based on latest eligible verified-profile analyses."},
        "branch_metrics": branch_metrics,
        "top_skill_deficits": deficits,
        "vulnerable_students": vulnerable,
        "vulnerable_threshold": s.vulnerable_lt,
        "category_labels": CATEGORY_LABELS,
    }


def _feature_benchmark(feature: str, db: Session) -> float | None:
    skill = db.execute(select(Skill).where(Skill.code == feature.upper())).scalars().first()
    if skill and skill.general_benchmark:
        return float(skill.general_benchmark)
    return {"sql_score": 70, "dsa_score": 65, "coding_score": 70, "programming_score": 70,
            "web_dev_score": 70, "communication_score": 65, "aptitude_score": 70,
            "logical_score": 70, "git_score": 65, "cloud_score": 55}.get(feature)


def skill_deficits(db: Session, branch: str | None = None, semester: int | None = None) -> dict:
    pairs = _base_query(db, branch, semester)
    per_skill: dict[str, dict] = {}
    for st, p, sc in pairs:
        snap = p.feature_snapshot or {}
        for feature, skill in FEATURE_TO_SKILL_REV.items():
            val = snap.get(feature)
            if val is None:
                continue
            bench = _feature_benchmark(feature, db)
            if bench is None:
                continue
            d = per_skill.setdefault(skill, {"n": 0, "below": 0, "sum": 0.0, "gap_sum": 0.0,
                                             "readiness_sum": 0.0, "feature": feature})
            d["n"] += 1
            d["sum"] += val
            d["readiness_sum"] += sc
            if val < bench:
                d["below"] += 1
                d["gap_sum"] += bench - val
    deficits = []
    for skill, d in per_skill.items():
        if d["n"] < 5:
            continue
        deficits.append({
            "skill": skill, "feature": d["feature"],
            "evaluated_count": d["n"], "below_benchmark_count": d["below"],
            "below_benchmark_percentage": round(d["below"] / d["n"] * 100, 1),
            "average_score": round(d["sum"] / d["n"], 1),
            "average_gap": round(d["gap_sum"] / d["below"], 1) if d["below"] else 0.0,
            "average_readiness": round(d["readiness_sum"] / d["n"], 1),
        })
    deficits.sort(key=lambda x: (-x["below_benchmark_percentage"], -x["below_benchmark_count"]))

    # heatmap: branch x skill
    cells: dict[str, dict[str, dict]] = {}
    for st, p, sc in pairs:
        snap = p.feature_snapshot or {}
        row = cells.setdefault(st.branch, {})
        for feature, skill in FEATURE_TO_SKILL_REV.items():
            val = snap.get(feature)
            if val is None:
                continue
            bench = _feature_benchmark(feature, db)
            if bench is None:
                continue
            c = row.setdefault(skill, {"n": 0, "below": 0, "sum": 0.0, "readiness_sum": 0.0})
            c["n"] += 1
            c["sum"] += val
            c["readiness_sum"] += sc
            if val < bench:
                c["below"] += 1
    heatmap = []
    for br in sorted(cells):
        for skill in HEATMAP_SKILLS:
            c = cells[br].get(skill)
            if not c or c["n"] < 5:
                continue
            heatmap.append({
                "branch": br, "skill": skill,
                "evaluated_count": c["n"], "below_benchmark_count": c["below"],
                "below_benchmark_percentage": round(c["below"] / c["n"] * 100, 1),
                "average_score": round(c["sum"] / c["n"], 1),
                "average_readiness": round(c["readiness_sum"] / c["n"], 1),
            })
    return {"status": "ok", "deficits": deficits, "heatmap": heatmap, "skills": HEATMAP_SKILLS}


def skill_drilldown(db: Session, skill: str, branch: str | None = None) -> dict:
    feature = next((f for f, sk in FEATURE_TO_SKILL_REV.items() if sk == skill), None)
    if feature is None:
        return {"status": "unknown_skill"}
    bench = _feature_benchmark(feature, db)
    pairs = _base_query(db, branch, None)
    rows = []
    for st, p, sc in pairs:
        val = (p.feature_snapshot or {}).get(feature)
        if val is None or val >= (bench or 0):
            continue
        xai = p.xai_json or {}
        rows.append({
            "student_id": st.id, "name": st.user.display_name if st.user else st.usn,
            "usn": st.usn, "branch": st.branch, "semester": st.semester,
            "score": val, "gap": round((bench or 0) - val, 1),
            "readiness": round(sc, 1), "category": p.category,
        })
    rows.sort(key=lambda r: r["score"])
    n = len(rows)
    return {
        "status": "ok", "skill": skill, "branch": branch, "benchmark": bench,
        "count": n,
        "average_score": round(sum(r["score"] for r in rows) / n, 1) if n else None,
        "average_readiness": round(sum(r["readiness"] for r in rows) / n, 1) if n else None,
        "students": rows[:100],
    }


def student_list(db: Session, search: str | None = None, branch: str | None = None,
                 semester: int | None = None, category: str | None = None,
                 min_score: float | None = None, max_score: float | None = None,
                 trust_min: float | None = None, page: int = 1, page_size: int = 20,
                 sort: str = "readiness") -> dict:
    pairs = _base_query(db, branch, semester, category, min_score, max_score)
    matches = db.execute(select(CareerMatch).where(CareerMatch.is_current == True)).scalars().all()  # noqa: E712
    best_career = {}
    for m in matches:
        cur = best_career.get(m.student_id)
        if cur is None or m.match_score > cur.match_score:
            best_career[m.student_id] = m

    rows = []
    for st, p, sc in pairs:
        if trust_min is not None and p.profile_trust < trust_min:
            continue
        if search:
            q = search.lower()
            name = st.user.display_name if st.user else ""
            if q not in name.lower() and q not in st.usn.lower():
                continue
        xai = p.xai_json or {}
        top_limiting = xai.get("limiting", [{}])[0].get("label") if xai.get("limiting") else None
        m = best_career.get(st.id)
        rows.append({
            "student_id": st.id, "name": st.user.display_name if st.user else st.usn,
            "usn": st.usn, "branch": st.branch, "semester": st.semester,
            "readiness": round(sc, 1), "category": p.category,
            "category_label": CATEGORY_LABELS[p.category],
            "best_career": m.career_code if m else None,
            "best_career_score": m.match_score if m else None,
            "primary_gap": top_limiting,
            "profile_trust": p.profile_trust,
            "data_completeness": p.data_completeness,
        })

    rows.sort(key=lambda r: (-r["readiness"] if sort == "readiness"
                             else (r["name"] or "").lower() if sort == "name"
                             else -r["profile_trust"]))
    total = len(rows)
    start = (page - 1) * page_size
    return {
        "status": "ok", "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "items": rows[start:start + page_size],
    }


def vulnerable_cohorts(db: Session, branch: str | None = None) -> list[dict]:
    s = get_settings()
    pairs = _base_query(db, branch, None)
    c: dict[str, list] = {}
    for st, p, sc in pairs:
        if sc < s.vulnerable_lt:
            c.setdefault(f"{st.branch} • Semester {st.semester}", []).append((st, p, sc))
    out = []
    for label, members in c.items():
        out.append({
            "label": label,
            "count": len(members),
            "average_readiness": round(sum(sc for _, _, sc in members) / len(members), 1),
        })
    out.sort(key=lambda x: -x["count"])
    return out


def student_summary(db: Session, student_id: int) -> dict | None:
    st = db.get(Student, student_id)
    if not st:
        return None
    p = db.execute(select(Prediction).where(
        Prediction.student_id == student_id, Prediction.is_current == True)).scalars().first()  # noqa: E712
    if not p:
        return None
    from app.services.analysis_service import get_current_prediction
    from app.services.career_service import latest_matches
    matches = latest_matches(db, st)
    xai = p.xai_json or {}
    return {
        "student": {"id": st.id, "name": st.user.display_name if st.user else st.usn,
                    "usn": st.usn, "branch": st.branch, "semester": st.semester},
        "readiness": {"score": round(p.probability * 100, 1), "category": p.category,
                      "category_label": CATEGORY_LABELS[p.category],
                      "model_version": p.model_version},
        "trust": p.profile_trust, "completeness": p.data_completeness,
        "career": matches[:2],
        "xai": {"positive": xai.get("positive", [])[:3], "limiting": xai.get("limiting", [])[:3]},
    }
