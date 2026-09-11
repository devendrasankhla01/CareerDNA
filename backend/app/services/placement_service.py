"""Placement pipeline — statuses, transitions, history, nomination, confirmation.

Human-controlled workflow (per spec):
  * student may express INTEREST (institution policy, config-gated);
  * TPO NOMINATES (only currently-eligible candidates under default policy);
  * company SHORTLISTS / INTERVIEW / SELECTS (recruiter actions, audited);
  * TPO CONFIRMS official placement (SELECTED -> PLACED). A company "Selected"
    never becomes the institution's placement record by itself.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import utcnow
from app.models import (
    CANDIDATE_STATUSES,
    CareerMatch,
    Certification,
    Company,
    Internship,
    PlacementCandidate,
    PlacementDrive,
    PlacementStatusHistory,
    Project,
    Student,
    StudentSkill,
    Skill,
    User,
)
from app.services import matching_service

# allowed status transitions: status -> set(next statuses)
TRANSITIONS: dict[str, set[str]] = {
    "INTERESTED": {"NOMINATED", "WITHDRAWN"},
    "NOMINATED": {"COMPANY_REVIEWING", "SHORTLISTED", "WITHDRAWN"},
    "COMPANY_REVIEWING": {"SHORTLISTED", "INTERVIEW", "WITHDRAWN"},
    "SHORTLISTED": {"INTERVIEW", "SELECTED", "NOT_SELECTED", "WITHDRAWN"},
    "INTERVIEW": {"SELECTED", "NOT_SELECTED", "WITHDRAWN"},
    "SELECTED": {"PLACED", "NOT_SELECTED"},
    "NOT_SELECTED": set(),
    "PLACED": set(),
    "WITHDRAWN": set(),
}


def get_candidate(db: Session, drive_id: int, student_id: int) -> PlacementCandidate | None:
    return db.execute(select(PlacementCandidate).where(
        PlacementCandidate.drive_id == drive_id,
        PlacementCandidate.student_id == student_id)).scalars().first()


def create_candidate(db: Session, drive_id: int, student_id: int, status: str = "INTERESTED",
                     actor: User | None = None, note: str | None = None) -> PlacementCandidate:
    c = get_candidate(db, drive_id, student_id)
    if c:
        return c
    c = PlacementCandidate(drive_id=drive_id, student_id=student_id, status=status)
    db.add(c)
    db.flush()
    _history(db, c, None, status, actor, note)
    return c


def _history(db: Session, c: PlacementCandidate, old: str | None, new: str,
             actor: User | None, note: str | None) -> None:
    db.add(PlacementStatusHistory(candidate_id=c.id, student_id=c.student_id,
                                  drive_id=c.drive_id, old_status=old, new_status=new,
                                  actor_id=actor.id if actor else None, note=note))


def express_interest(db: Session, user: User, drive_id: int) -> PlacementCandidate:
    s = get_settings()
    if user.role != "STUDENT":
        raise HTTPException(403, "Students can only express interest in their own opportunities")
    st = db.execute(select(Student).where(Student.user_id == user.id)).scalars().first()
    if not st:
        raise HTTPException(404, "Student profile not found")
    drive = db.get(PlacementDrive, drive_id)
    if not drive or drive.status != "OPEN":
        raise HTTPException(404, "Drive is not open")
    if not s.allow_student_interest:
        raise HTTPException(403, "Institution policy does not currently allow student interest")
    c = get_candidate(db, drive_id, st.id)
    if c and c.status != "INTERESTED":
        return c
    if c is None:
        c = create_candidate(db, drive_id, st.id, "INTERESTED", actor=user, note="Student expressed interest")
    db.commit()
    return c


def nominate(db: Session, tpo: User, drive_id: int, student_ids: list[int],
             note: str | None = None) -> dict:
    """TPO nomination. Default policy: only currently-eligible students."""
    if tpo.role != "TPO_ADMIN":
        raise HTTPException(403, "Only the TPO can nominate")
    drive = db.get(PlacementDrive, drive_id)
    if not drive:
        raise HTTPException(404, "Drive not found")
    inp = matching_service._load_inputs(db)
    weights = get_settings().company_match_weights
    nominated, skipped = [], []
    for sid in student_ids:
        st = db.get(Student, sid)
        if st is None or not st.is_active:
            skipped.append({"student_id": sid, "reason": "not found or inactive"})
            continue
        r = matching_service.evaluate_one(drive, st, inp.get(sid, {}), weights)
        if r is None:
            skipped.append({"student_id": sid, "reason": "not analyzed"})
            continue
        if not r["eligible"]:
            skipped.append({"student_id": sid, "reason": "no longer meets mandatory criteria",
                            "blockers": r["mandatory_blockers"]})
            continue
        c = get_candidate(db, drive_id, sid)
        if c is None:
            c = create_candidate(db, drive_id, sid, "INTERESTED", actor=None)
        if c.status == "INTERESTED":
            c.status = "NOMINATED"
        elif c.status not in ("NOMINATED",):
            # already further along; do not regress
            db.commit()
            continue
        c.nominated_by = tpo.id
        c.nominated_at = utcnow()
        _history(db, c, "INTERESTED", "NOMINATED", tpo, note)
        nominated.append(sid)
    db.commit()
    return {"nominated": len(nominated), "skipped": skipped}


def company_transition(db: Session, user: User, drive_id: int, student_id: int,
                       new_status: str, note: str | None = None) -> PlacementCandidate:
    """Company recruiter moves a candidate to a recruitment stage."""
    if user.role != "COMPANY":
        raise HTTPException(403, "Company access required")
    drive = db.get(PlacementDrive, drive_id)
    if not drive or drive.company_id != user.company_id:
        raise HTTPException(403, "This drive is not authorized for your company")
    if new_status not in CANDIDATE_STATUSES:
        raise HTTPException(400, f"Unknown status {new_status}")
    c = get_candidate(db, drive_id, student_id)
    if not c:
        raise HTTPException(404, "Candidate not in this drive")
    if new_status not in TRANSITIONS.get(c.status, set()):
        raise HTTPException(409, f"Cannot move {c.status} -> {new_status}")
    old = c.status
    c.status = new_status
    if new_status == "SHORTLISTED" and not c.shortlisted_at:
        c.shortlisted_at = utcnow()
    if new_status == "SELECTED":
        c.selected_by = user.id
        c.selected_at = utcnow()
        c.selection_note = note
    _history(db, c, old, new_status, user, note)
    db.commit()
    return c


def confirm_placement(db: Session, tpo: User, candidate_id: int,
                      note: str | None = None) -> PlacementCandidate:
    """TPO confirms the official institutional placement (SELECTED -> PLACED)."""
    if tpo.role != "TPO_ADMIN":
        raise HTTPException(403, "Only the TPO can confirm a placement")
    c = db.get(PlacementCandidate, candidate_id)
    if not c:
        raise HTTPException(404, "Candidate record not found")
    if c.status != "SELECTED":
        raise HTTPException(409, "Only company-selected candidates can be confirmed")
    old = c.status
    c.status = "PLACED"
    c.confirmed_by = tpo.id
    c.confirmed_at = utcnow()
    _history(db, c, old, "PLACED", tpo, note or "Placement confirmed by TPO")
    db.commit()
    return c


# ---------------------------------------------------------------- views
COMPANY_VISIBLE_STATUSES = ("NOMINATED", "COMPANY_REVIEWING", "SHORTLISTED",
                            "INTERVIEW", "SELECTED", "PLACED", "NOT_SELECTED")


def drive_pipeline(db: Session, drive: PlacementDrive,
                   student_ids: set[int] | None = None) -> dict:
    """Eligible -> Interested -> Nominated -> Shortlisted -> Interview -> Selected -> Placed."""
    ids = student_ids
    if ids is None:
        ids = {s.id for s in db.execute(select(Student).where(Student.is_active == True)).scalars()}  # noqa: E712
    matches = matching_service.matches_for_drive(db, drive, ids)
    cands = {c.student_id: c for c in db.execute(
        select(PlacementCandidate).where(PlacementCandidate.drive_id == drive.id)).scalars()}
    counts = {"eligible": 0, "almost_eligible": 0, "not_eligible": 0, "interested": 0,
              "nominated": 0, "reviewing": 0, "shortlisted": 0, "interview": 0,
              "selected": 0, "placed": 0, "not_selected": 0, "analyzed": len(matches)}
    for m in matches:
        c = cands.get(m["student_id"])
        if m["eligible"]:
            counts["eligible"] += 1
        elif m["almost_eligible"]:
            counts["almost_eligible"] += 1
        else:
            counts["not_eligible"] += 1
        if c:
            key = {"INTERESTED": "interested", "NOMINATED": "nominated",
                   "COMPANY_REVIEWING": "reviewing", "SHORTLISTED": "shortlisted",
                   "INTERVIEW": "interview", "SELECTED": "selected", "PLACED": "placed",
                   "NOT_SELECTED": "not_selected"}.get(c.status)
            if key:
                counts[key] += 1
    # common blockers across non-eligible students
    from collections import Counter
    blockers = Counter()
    label_by_key: dict[str, str] = {}
    for m in matches:
        for b in m["mandatory_blockers"]:
            label_by_key.setdefault(b["key"], b["label"])
        if not m["eligible"]:
            for b in m["mandatory_blockers"]:
                blockers[b["key"]] += 1
    counts["common_blockers"] = [
        {"key": k, "label": label_by_key.get(k, k), "count": n}
        for k, n in blockers.most_common(5)]
    return counts


def company_candidate_detail(db: Session, user: User, drive_id: int, student_id: int) -> dict:
    """Recruitment-relevant, privacy-filtered candidate profile."""
    drive = db.get(PlacementDrive, drive_id)
    if not drive or drive.company_id != user.company_id:
        raise HTTPException(403, "Drive not authorized for your company")
    c = get_candidate(db, drive_id, student_id)
    if not c or c.status == "INTERESTED":
        raise HTTPException(404, "Candidate not visible to your company")
    st = db.get(Student, student_id)
    if not st:
        raise HTTPException(404, "Student not found")
    skills = {sk.code: row.score for row, sk in db.execute(
        select(StudentSkill, Skill)
        .where(StudentSkill.student_id == student_id, StudentSkill.status == "VERIFIED")
        .join(Skill, StudentSkill.skill_id == Skill.id)).all()}
    projects = [{"title": p.title, "tech_stack": p.tech_stack,
                 "complexity": p.verified_complexity or p.claimed_complexity,
                 "type": p.project_type} for p in st.projects if p.status == "VERIFIED"]
    internships = [{"organization": i.organization, "role": i.role,
                    "domain": i.domain} for i in st.internships if i.status == "VERIFIED"]
    certs = [{"name": ct.name, "issuer": ct.issuer} for ct in st.certifications if ct.status == "VERIFIED"]
    inp = matching_service._load_inputs(db).get(student_id, {})
    best_career = max(inp.get("career", {}).items(), key=lambda kv: kv[1], default=(None, 0))
    r = matching_service.evaluate_one(drive, st, inp, get_settings().company_match_weights)
    # privacy: no emails, no storage paths, no internal notes, no other companies
    return {
        "status": "ok",
        "student": {
            "id": st.id, "name": st.user.display_name if st.user else st.usn,
            "usn": st.usn, "branch": st.branch, "semester": st.semester,
            "cgpa": inp.get("cgpa"),
        },
        "analysis": {
            "readiness": inp.get("readiness"),
            "category": inp.get("category"),
            "verification_coverage": inp.get("coverage"),
            "company_match": r["match_score"] if r else None,
            "eligible": r["eligible"] if r else None,
            "career_best": best_career[0],
            "career_score": round(best_career[1], 1) if best_career[0] else None,
            "top_strengths": r.get("required_matches", [])[:4] if r else [],
            "development_areas": r.get("improvement_opportunities", [])[:3] if r else [],
            "explanation": r.get("explanation", [])[:3] if r else [],
        },
        "verified": {
            "skills": skills,
            "projects": projects,
            "internships": internships,
            "certifications": certs,
        },
        "candidate": {
            "status": c.status,
            "match_score": c.match_score,
            "shortlisted_at": c.shortlisted_at.isoformat() if c.shortlisted_at else None,
            "selected_at": c.selected_at.isoformat() if c.selected_at else None,
            "selected_note": c.selection_note,
        },
    }


def student_journey(db: Session, st: Student) -> list[dict]:
    cands = db.execute(select(PlacementCandidate).where(
        PlacementCandidate.student_id == st.id)).scalars().all()
    out = []
    for c in sorted(cands, key=lambda x: x.updated_at, reverse=True):
        d = db.get(PlacementDrive, c.drive_id)
        out.append({
            "candidate_id": c.id,
            "drive_id": d.id if d else None,
            "company": d.company.name if d else None,
            "role": d.role if d else None,
            "title": d.title if d else None,
            "status": c.status,
            "match_score": c.match_score,
            "updated_at": c.updated_at.isoformat(),
            "confirmed_at": c.confirmed_at.isoformat() if c.confirmed_at else None,
        })
    return out


def placements_list(db: Session) -> dict:
    """Institution placement overview (TPO)."""
    cands = db.execute(select(PlacementCandidate)).scalars().all()
    students = {s.id: s for s in db.execute(select(Student)).scalars()}
    rows = []
    for c in cands:
        st = students.get(c.student_id)
        d = db.get(PlacementDrive, c.drive_id)
        if not st or not d or c.status not in ("SELECTED", "PLACED", "NOT_SELECTED"):
            continue
        rows.append({
            "candidate_id": c.id,
            "student_id": st.id,
            "name": st.user.display_name if st.user else st.usn,
            "usn": st.usn, "branch": st.branch, "semester": st.semester,
            "readiness": c.match_score and None,  # filled below
            "company": d.company.name, "drive": d.title, "role": d.role,
            "ctc": d.ctc,
            "status": c.status,
            "readiness": None,
            "selected_at": c.selected_at.isoformat() if c.selected_at else None,
            "confirmed_at": c.confirmed_at.isoformat() if c.confirmed_at else None,
        })
    inp = matching_service._load_inputs(db)
    for r in rows:
        r["readiness"] = inp.get(r["student_id"], {}).get("readiness")
    counts = {
        "placed": sum(1 for r in rows if r["status"] == "PLACED"),
        "selected": sum(1 for r in rows if r["status"] == "SELECTED"),
        "not_selected": sum(1 for r in rows if r["status"] == "NOT_SELECTED"),
    }
    participated = {c.student_id for c in cands}
    return {"rows": sorted(rows, key=lambda r: (r["status"] != "PLACED", r["status"] != "SELECTED")),
            "counts": counts,
            "participating_students": len(participated)}
