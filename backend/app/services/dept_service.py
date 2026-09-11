"""Department dashboard service — strictly scoped to one department (branch).

Department staff can: monitor readiness/skills/placement for THEIR students,
and update institution-owned data they are authorized to maintain (semester,
CGPA, backlogs, assessment scores) — every change is audited. They cannot
edit model outputs, verify evidence, or confirm placements.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AcademicRecord,
    CareerMatch,
    PlacementCandidate,
    PlacementDrive,
    Prediction,
    Skill,
    Student,
    StudentSkill,
    User,
)
from app.services import matching_service
from app.core.security import utcnow


def dept_students(db: Session, dept_code: str) -> list[Student]:
    return db.execute(select(Student).where(
        Student.is_active == True, Student.branch == dept_code)).scalars().all()  # noqa: E712


def _enrich(db: Session, students: list[Student]) -> list[dict]:
    preds = {p.student_id: p for p in db.execute(
        select(Prediction).where(Prediction.is_current == True)).scalars()}  # noqa: E712
    careers = {}
    for m in db.execute(select(CareerMatch).where(CareerMatch.is_current == True)).scalars():  # noqa: E712
        cur = careers.get(m.student_id)
        if cur is None or m.match_score > cur.match_score:
            careers[m.student_id] = m
    acads = {a.student_id: a for a in db.execute(select(AcademicRecord)).scalars()}
    cands = {}
    for c in db.execute(select(PlacementCandidate)).scalars():
        cands.setdefault(c.student_id, []).append(c)
    # eligible company count per student (open drives only)
    drives = db.execute(select(PlacementDrive).where(PlacementDrive.status == "OPEN")).scalars().all()
    weights = None
    eligible_count: dict[int, int] = {}
    if drives:
        inp = matching_service._load_inputs(db)
        weights = __import__("app.core.config", fromlist=["get_settings"]).get_settings().company_match_weights
        for st in students:
            n = 0
            for d in drives:
                r = matching_service.evaluate_one(d, st, inp.get(st.id, {}), weights)
                if r and r["eligible"]:
                    n += 1
            eligible_count[st.id] = n
    out = []
    for st in students:
        p = preds.get(st.id)
        xai = (p.xai_json or {}) if p else {}
        top_gap = None
        if xai.get("limiting"):
            top_gap = xai["limiting"][0].get("label")
        m = careers.get(st.id)
        a = acads.get(st.id)
        active_status = None
        for c in sorted(cands.get(st.id, []), key=lambda x: x.updated_at, reverse=True):
            if c.status in ("NOMINATED", "COMPANY_REVIEWING", "SHORTLISTED", "INTERVIEW", "SELECTED", "PLACED"):
                active_status = c.status
                break
        out.append({
            "student_id": st.id,
            "name": st.user.display_name if st.user else st.usn,
            "usn": st.usn, "semester": st.semester,
            "readiness": round(p.probability * 100, 1) if p else None,
            "category": p.category if p else None,
            "career_best": m.career_code if m else None,
            "career_score": m.match_score if m else None,
            "cgpa": a.cgpa if a else None,
            "top_gap": top_gap,
            "verification_coverage": p.profile_trust if p else 0,
            "eligible_companies": eligible_count.get(st.id, 0),
            "placement_status": active_status,
        })
    return out


def overview(db: Session, dept_code: str) -> dict:
    students = dept_students(db, dept_code)
    rows = _enrich(db, students)
    analyzed = [r for r in rows if r["readiness"] is not None]
    from collections import Counter
    cats = Counter(r["category"] for r in analyzed)
    total = len(rows)
    avg = round(sum(r["readiness"] for r in analyzed) / len(analyzed), 1) if analyzed else None
    # pipeline (department scope)
    from app.services import placement_service
    cands = db.execute(select(PlacementCandidate)).scalars().all()
    sid_set = {st.id for st in students}
    pl = Counter(c.status for c in cands if c.student_id in sid_set)
    top_gaps = Counter(r["top_gap"] for r in analyzed if r["top_gap"]).most_common(5)
    return {
        "status": "ok",
        "department": dept_code,
        "population": {"total": total, "analyzed": len(analyzed),
                       "not_analyzed": total - len(analyzed)},
        "readiness": {
            "ready": cats.get("READY", 0), "near_ready": cats.get("NEAR_READY", 0),
            "needs_training": cats.get("NEEDS_TRAINING", 0),
            "average": avg,
        },
        "verification_coverage": round(sum(r["verification_coverage"] for r in analyzed) / len(analyzed), 1)
        if analyzed else 0,
        "placement_eligible": sum(1 for r in rows if r["eligible_companies"] > 0),
        "pipeline": {
            "nominated": pl.get("NOMINATED", 0), "shortlisted": pl.get("SHORTLISTED", 0),
            "interview": pl.get("INTERVIEW", 0), "selected": pl.get("SELECTED", 0),
            "placed": pl.get("PLACED", 0), "not_selected": pl.get("NOT_SELECTED", 0),
        },
        "top_gaps": [{"label": k, "count": n} for k, n in top_gaps],
        "students": rows,
    }


def skill_gaps(db: Session, dept_code: str) -> dict:
    """Same deficit/heatmap math as TPO, scoped to one department."""
    students = dept_students(db, dept_code)
    ids = {st.id for st in students}
    from app.services.tpo_service import _base_query
    pairs = [(st, p, sc) for (st, p, sc) in _base_query(db) if st.id in ids]
    from app.services.tpo_service import HEATMAP_SKILLS, FEATURE_TO_SKILL_REV, _feature_benchmark
    per_skill: dict[str, dict] = {}
    sems: dict[str, dict] = {}
    for st, p, sc in pairs:
        snap = p.feature_snapshot or {}
        for feature, skill in FEATURE_TO_SKILL_REV.items():
            val = snap.get(feature)
            if val is None:
                continue
            bench = _feature_benchmark(feature, db)
            if bench is None:
                continue
            d = per_skill.setdefault(skill, {"n": 0, "below": 0, "sum": 0.0, "gap_sum": 0.0})
            d["n"] += 1
            d["sum"] += val
            if val < bench:
                d["below"] += 1
                d["gap_sum"] += bench - val
            s = sems.setdefault(st.semester, {}).setdefault(
                skill, {"n": 0, "below": 0})
            s["n"] += 1
            if val < bench:
                s["below"] += 1
    deficits = []
    for skill, d in per_skill.items():
        if d["n"] < 3:
            continue
        deficits.append({
            "skill": skill, "evaluated_count": d["n"], "below_benchmark_count": d["below"],
            "below_benchmark_percentage": round(d["below"] / d["n"] * 100, 1),
            "average_score": round(d["sum"] / d["n"], 1),
            "average_gap": round(d["gap_sum"] / d["below"], 1) if d["below"] else 0.0,
        })
    deficits.sort(key=lambda x: (-x["below_benchmark_percentage"], -x["below_benchmark_count"]))
    heatmap = []
    for sem in sorted(sems):
        for skill in HEATMAP_SKILLS:
            c = sems[sem].get(skill)
            if not c or c["n"] < 3:
                continue
            heatmap.append({"semester": sem, "skill": skill, "n": c["n"],
                            "below_benchmark_count": c["below"],
                            "below_benchmark_percentage": round(c["below"] / c["n"] * 100, 1)})
    return {"status": "ok", "deficits": deficits, "heatmap": heatmap, "skills": HEATMAP_SKILLS}


def performance(db: Session, dept_code: str) -> dict:
    students = dept_students(db, dept_code)
    ids = {st.id for st in students}
    acads = [a for a in db.execute(select(AcademicRecord)).scalars() if a.student_id in ids]
    skills = {}
    for row, sk in db.execute(
            select(StudentSkill, Skill)
            .where(StudentSkill.student_id.in_(ids), StudentSkill.status == "VERIFIED")
            .join(Skill, StudentSkill.skill_id == Skill.id)).all():
        skills.setdefault(sk.code, []).append(row.score or 0)
    from app.services.tpo_service import _base_query
    pairs = [(st, p, sc) for (st, p, sc) in _base_query(db) if st.id in ids]
    careers = {}
    for m in db.execute(select(CareerMatch).where(
            CareerMatch.student_id.in_(ids), CareerMatch.is_current == True)).scalars():  # noqa: E712
        careers.setdefault(m.career_code, 0)
        careers[m.career_code] += 1
    return {
        "status": "ok",
        "academic": {
            "avg_cgpa": round(sum(a.cgpa for a in acads) / len(acads), 2) if acads else None,
            "avg_tenth": round(sum(a.tenth_percentage or 0 for a in acads) / len(acads), 1) if acads else None,
            "avg_twelfth": round(sum(a.twelfth_percentage or 0 for a in acads) / len(acads), 1) if acads else None,
            "avg_backlogs": round(sum(a.backlog_history_count for a in acads) / len(acads), 2) if acads else None,
            "records": len(acads),
        },
        "skills": {k: round(sum(v) / len(v), 1) for k, v in skills.items() if len(v) >= 3},
        "readiness_distribution": {
            "ready": sum(1 for _, p, _ in pairs if p.category == "READY"),
            "near_ready": sum(1 for _, p, _ in pairs if p.category == "NEAR_READY"),
            "needs_training": sum(1 for _, p, _ in pairs if p.category == "NEEDS_TRAINING"),
        },
        "career_alignment": careers,
    }


def company_eligibility(db: Session, dept_code: str) -> dict:
    students = dept_students(db, dept_code)
    inp = matching_service._load_inputs(db)
    weights = __import__("app.core.config", fromlist=["get_settings"]).get_settings().company_match_weights
    drives = db.execute(select(PlacementDrive).where(
        PlacementDrive.status.in_(("OPEN", "DRAFT")))).scalars().all()
    out = []
    for d in drives:
        matches = [matching_service.evaluate_one(d, st, inp.get(st.id, {}), weights)
                   for st in students if inp.get(st.id, {}).get("readiness") is not None]
        matches = [m for m in matches if m]
        from collections import Counter
        blockers = Counter()
        for m in matches:
            if not m["eligible"]:
                for b in m["mandatory_blockers"]:
                    blockers[b["key"]] += 1
        top = blockers.most_common(1)
        label = {
            "cgpa": "CGPA", "tenth": "10th %", "twelfth": "12th %", "backlog": "Backlog policy",
            "readiness": "Readiness", "coding": "Coding score", "aptitude": "Aptitude score",
            "communication": "Communication", "project": "Verified project",
            "internship": "Verified internship", "branch": "Branch", "semester": "Semester",
        }.get(top[0][0], top[0][0]) if top else None
        out.append({
            "drive_id": d.id, "company": d.company.name, "role": d.role,
            "title": d.title, "status": d.status, "drive_date": d.drive_date,
            "analyzed": len(matches),
            "eligible": sum(1 for m in matches if m["eligible"]),
            "almost_eligible": sum(1 for m in matches if m["almost_eligible"]),
            "not_eligible": sum(1 for m in matches if not m["eligible"]),
            "one_actionable_gap": sum(1 for m in matches if m["almost_eligible"]
                                      and len(m["actionable_blockers"]) == 1),
            "top_blocker": label,
            "top_blocker_count": top[0][1] if top else 0,
        })
    out.sort(key=lambda x: -(x["eligible"]))
    return {"status": "ok", "drives": out}


def placement_status(db: Session, dept_code: str) -> dict:
    students = dept_students(db, dept_code)
    sid = {st.id: st for st in students}
    cands = db.execute(select(PlacementCandidate)).scalars().all()
    drives = {d.id: d for d in db.execute(select(PlacementDrive)).scalars()}
    rows = []
    for c in sorted(cands, key=lambda x: x.updated_at, reverse=True):
        if c.student_id not in sid:
            continue
        st = sid[c.student_id]
        d = drives.get(c.drive_id)
        rows.append({
            "student_id": st.id, "name": st.user.display_name if st.user else st.usn,
            "usn": st.usn, "semester": st.semester,
            "company": d.company.name if d else None, "role": d.role if d else None,
            "drive": d.title if d else None, "status": c.status,
            "updated_at": c.updated_at.isoformat(),
        })
    return {"status": "ok", "rows": rows}


# ---------------------------------------------------------------- data updates
DEPT_EDITABLE_SKILLS = {"CODING", "APTITUDE", "LOGICAL", "COMMUNICATION", "PRESENTATION"}
DEPT_CSV_COLUMNS = {"usn", "cgpa", "semester", "backlog_history_count", "backlogs",
                    "tenth_percentage", "twelfth_percentage",
                    "coding", "aptitude", "logical", "communication", "presentation"}


def update_student(db: Session, dept_user: User, student_id: int, updates: dict) -> dict:
    """Authorized department data updates (institution-owned fields only)."""
    if dept_user.role not in ("DEPARTMENT", "TPO_ADMIN"):
        raise HTTPException(403, "Department access required")
    st = db.get(Student, student_id)
    if not st:
        raise HTTPException(404, "Student not found")
    if dept_user.role == "DEPARTMENT" and st.branch != (dept_user.department.code if dept_user.department else None):
        raise HTTPException(403, "Student is not in your department")
    allowed = {"semester", "cgpa", "backlog_history_count", "tenth_percentage",
               "twelfth_percentage"} | DEPT_EDITABLE_SKILLS
    bad = set(updates) - allowed
    if bad:
        raise HTTPException(400, f"Fields not editable by departments: {', '.join(sorted(bad))}")
    audit = []
    ac = db.execute(select(AcademicRecord).where(
        AcademicRecord.student_id == student_id)).scalars().first()
    for k in ("cgpa", "tenth_percentage", "twelfth_percentage", "backlog_history_count"):
        if k in updates and updates[k] is not None:
            v = float(updates[k]) if k != "backlog_history_count" else int(updates[k])
            old = getattr(ac, k, None) if ac else None
            if ac:
                setattr(ac, k, v)
            else:
                ac = AcademicRecord(student_id=student_id,
                                    cgpa=updates.get("cgpa", 0.0) if updates.get("cgpa") is not None else 0.0,
                                    tenth_percentage=updates.get("tenth_percentage"),
                                    twelfth_percentage=updates.get("twelfth_percentage"),
                                    backlog_history_count=updates.get("backlog_history_count", 0))
                db.add(ac)
            audit.append({"field": k, "before": old, "after": v})
    if "semester" in updates and updates["semester"] is not None:
        old = st.semester
        st.semester = int(updates["semester"])
        audit.append({"field": "semester", "before": old, "after": st.semester})
    skills = {sk.code: row for row, sk in db.execute(
        select(StudentSkill, Skill)
        .where(StudentSkill.student_id == student_id)
        .join(Skill, StudentSkill.skill_id == Skill.id)).all()}
    for code in DEPT_EDITABLE_SKILLS:
        if code in updates and updates[code] is not None:
            v = float(updates[code])
            old = skills[code].score if code in skills else None
            if code in skills:
                skills[code].score = v
                skills[code].source = "INSTITUTION"
                skills[code].status = "VERIFIED"
            else:
                sk = db.execute(select(Skill).where(Skill.code == code)).scalars().first()
                if sk:
                    db.add(StudentSkill(student_id=student_id, skill_id=sk.id, score=v,
                                        source="INSTITUTION", status="VERIFIED"))
            audit.append({"field": f"skill:{code}", "before": old, "after": v})
    # audit via AcademicIssue-style history: store on student profile version bump
    st.profile_version += 1
    db.commit()
    # re-analyze so readiness reflects the updated institution data
    from app.services.analysis_service import run_analysis
    run_analysis(db, st, reason="department_update")
    db.commit()
    return {"status": "ok", "student_id": student_id, "audit": audit,
            "actor": dept_user.display_name, "at": utcnow().isoformat()}


def bulk_update(db: Session, dept_user: User, rows: list[dict]) -> dict:
    updated, errors = 0, []
    for i, row in enumerate(rows, start=2):
        usn = str(row.get("usn", "")).strip().upper()
        try:
            st = db.execute(select(Student).where(Student.usn == usn)).scalars().first()
            if not st:
                errors.append({"row": i, "usn": usn, "errors": ["student not found"]})
                continue
            if dept_user.role == "DEPARTMENT" and st.branch != (
                    dept_user.department.code if dept_user.department else None):
                errors.append({"row": i, "usn": usn, "errors": ["not in your department"]})
                continue
            updates = {}
            for k in ("cgpa", "tenth_percentage", "twelfth_percentage"):
                if row.get(k) not in (None, ""):
                    updates[k] = float(row[k])
            for k in ("backlog_history_count", "backlogs"):
                if row.get(k) not in (None, ""):
                    updates["backlog_history_count"] = int(float(row[k]))
                    break
            if "semester" in row and row.get("semester") not in (None, ""):
                updates["semester"] = int(float(row["semester"]))
            for code in DEPT_EDITABLE_SKILLS:
                if row.get(code) not in (None, ""):
                    updates[code] = float(row[code])
            if not updates:
                continue
            update_student(db, dept_user, st.id, updates)
            updated += 1
        except (ValueError, TypeError) as e:
            errors.append({"row": i, "usn": usn, "errors": [str(e)]})
    return {"status": "ok", "updated": updated, "errors": errors[:100]}
