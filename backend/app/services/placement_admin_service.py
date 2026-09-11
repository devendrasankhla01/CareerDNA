"""TPO placement administration: companies, drives, verification center,
department comparison. All institution-wide (TPO is the operational authority).
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password, utcnow
from app.models import (
    Company,
    Department,
    FacultyCategory,
    PlacementCandidate,
    PlacementDrive,
    User,
    VerificationAssignment,
    VerificationRequest,
)
from app.services import placement_service

# criteria fields that bump criteria_version when changed
CRITERIA_FIELDS = {
    "min_cgpa", "min_tenth", "min_twelfth", "max_backlogs", "min_readiness",
    "min_coding", "min_aptitude", "min_communication", "project_required",
    "internship_required", "target_branches", "eligible_semesters",
    "required_skills", "preferred_skills", "preferred_career_code",
}


def list_companies(db: Session) -> dict:
    comps = db.execute(select(Company).order_by(Company.name)).scalars().all()
    out = []
    for c in comps:
        drives = db.execute(select(PlacementDrive).where(
            PlacementDrive.company_id == c.id)).scalars().all()
        cand = db.execute(select(PlacementCandidate).where(
            PlacementCandidate.drive_id.in_([d.id for d in drives]))).scalars().all() if drives else []
        out.append({
            "id": c.id, "name": c.name, "industry": c.industry, "website": c.website,
            "description": c.description, "location": c.location, "status": c.status,
            "created_at": c.created_at.isoformat(),
            "active_drives": sum(1 for d in drives if d.status == "OPEN"),
            "total_drives": len(drives),
            "nominated": sum(1 for x in cand if x.status in ("NOMINATED", "COMPANY_REVIEWING", "SHORTLISTED", "INTERVIEW", "SELECTED", "PLACED")),
            "shortlisted": sum(1 for x in cand if x.status in ("SHORTLISTED", "INTERVIEW", "SELECTED", "PLACED")),
            "selected": sum(1 for x in cand if x.status in ("SELECTED", "PLACED")),
        })
    return {"status": "ok", "companies": out}


def create_company(db: Session, tpo: User, data: dict) -> Company:
    c = Company(
        name=data["name"].strip(), industry=data.get("industry"), website=data.get("website"),
        description=data.get("description"), location=data.get("location"),
        status=data.get("status", "ACTIVE"), created_by=tpo.id)
    db.add(c)
    db.flush()
    # optional recruiter account in the same step
    if data.get("recruiter_email"):
        email = data["recruiter_email"].strip().lower()
        exists = db.execute(select(User).where(User.email == email)).scalars().first()
        if exists:
            raise HTTPException(409, f"An account with {email} already exists")
        db.add(User(role="COMPANY", email=email,
                    password_hash=hash_password(data["recruiter_password"]),
                    display_name=data.get("recruiter_name") or "Recruiter",
                    company_id=c.id))
    db.commit()
    return c


def update_company(db: Session, tpo: User, company_id: int, data: dict) -> Company:
    c = db.get(Company, company_id)
    if not c:
        raise HTTPException(404, "Company not found")
    for k in ("name", "industry", "website", "description", "location", "status"):
        if k in data and data[k] is not None:
            setattr(c, k, data[k])
    db.commit()
    return c


def list_drives(db: Session, company_id: int | None = None) -> dict:
    q = select(PlacementDrive).order_by(PlacementDrive.created_at.desc())
    if company_id:
        q = q.where(PlacementDrive.company_id == company_id)
    drives = db.execute(q).scalars().all()
    out = []
    for d in drives:
        cands = db.execute(select(PlacementCandidate).where(
            PlacementCandidate.drive_id == d.id)).scalars().all()
        out.append({
            "id": d.id, "company_id": d.company_id, "company": d.company.name,
            "title": d.title, "role": d.role, "location": d.location,
            "ctc": d.ctc, "drive_date": d.drive_date, "deadline": d.deadline,
            "open_positions": d.open_positions, "status": d.status,
            "criteria_version": d.criteria_version,
            "min_cgpa": d.min_cgpa, "min_readiness": d.min_readiness,
            "required_skills": d.required_skills, "preferred_skills": d.preferred_skills,
            "target_branches": d.target_branches, "eligible_semesters": d.eligible_semesters,
            "nominated": sum(1 for x in cands if x.status != "INTERESTED"),
            "shortlisted": sum(1 for x in cands if x.status in ("SHORTLISTED", "INTERVIEW", "SELECTED", "PLACED")),
            "selected": sum(1 for x in cands if x.status in ("SELECTED", "PLACED")),
            "created_at": d.created_at.isoformat(),
        })
    return {"status": "ok", "drives": out}


def _apply_drive(db: Session, d: PlacementDrive, data: dict) -> bool:
    """Apply fields; return True if a criteria-relevant field changed."""
    changed = False
    for k in ("title", "role", "job_description", "location", "ctc", "employment_type",
              "drive_date", "deadline", "open_positions", "status"):
        if k in data and data[k] is not None:
            setattr(d, k, data[k])
    for k in CRITERIA_FIELDS:
        if k in data:
            setattr(d, k, data[k])
            changed = True
    if changed:
        d.criteria_version += 1
    return changed


def create_drive(db: Session, tpo: User, data: dict) -> PlacementDrive:
    company = db.get(Company, data["company_id"])
    if not company:
        raise HTTPException(404, "Company not found")
    d = PlacementDrive(company_id=company.id, created_by=tpo.id, **{
        k: v for k, v in data.items() if k != "company_id"})
    db.add(d)
    db.commit()
    return d


def update_drive(db: Session, tpo: User, drive_id: int, data: dict) -> PlacementDrive:
    d = db.get(PlacementDrive, drive_id)
    if not d:
        raise HTTPException(404, "Drive not found")
    _apply_drive(db, d, data)
    db.commit()
    return d


def set_drive_status(db: Session, tpo: User, drive_id: int, status: str) -> PlacementDrive:
    if status not in ("DRAFT", "OPEN", "CLOSED", "COMPLETED"):
        raise HTTPException(400, f"Unknown drive status {status}")
    d = db.get(PlacementDrive, drive_id)
    if not d:
        raise HTTPException(404, "Drive not found")
    d.status = status
    db.commit()
    return d


# ---------------------------------------------------------------- verification center
def verification_center(db: Session, filters: dict | None = None) -> dict:
    f = filters or {}
    reqs = db.execute(select(VerificationRequest)).scalars().all()
    assigned = {a.request_id: a for a in db.execute(
        select(VerificationAssignment).where(
            VerificationAssignment.status == "PENDING")).scalars()}
    verifiers = {u.id: u for u in db.execute(
        select(User).where(User.role.in_(["FACULTY", "VERIFIER"]))).scalars()}
    s = get_settings()
    cutoff = utcnow() - timedelta(days=s.verification_escalation_days)
    counts = {"pending": 0, "assigned": 0, "unassigned": 0, "correction_required": 0,
              "verified": 0, "verified_today": 0, "escalated": 0, "rejected": 0}
    rows = []
    from app.models import Student
    from app.models import VerificationReview
    for r in reqs:
        if f.get("status") and r.status != f["status"]:
            continue
        st = db.get(Student, r.student_id)
        a = assigned.get(r.id)
        age_days = (utcnow() - r.submitted_at).days
        escalated = r.status == "PENDING" and r.submitted_at < cutoff
        if r.status == "PENDING":
            counts["pending"] += 1
            if a:
                counts["assigned"] += 1
            else:
                counts["unassigned"] += 1
            if escalated:
                counts["escalated"] += 1
        elif r.status == "CORRECTION_REQUIRED":
            counts["correction_required"] += 1
        elif r.status == "VERIFIED":
            counts["verified"] += 1
            last = db.execute(select(VerificationReview).where(
                VerificationReview.request_id == r.id).order_by(
                VerificationReview.reviewed_at.desc())).scalars().first()
            if last and last.reviewed_at.date() == utcnow().date():
                counts["verified_today"] += 1
        elif r.status == "REJECTED":
            counts["rejected"] += 1
        if f.get("department") and st and st.branch != f["department"]:
            continue
        if f.get("category") and r.category != f["category"]:
            continue
        if f.get("verifier") and (a.verifier_id if a else None) != int(f["verifier"]):
            continue
        rows.append({
            "request_id": r.id, "status": r.status,
            "student_name": st.user.display_name if st and st.user else None,
            "usn": st.usn if st else None, "branch": st.branch if st else None,
            "entity_type": r.entity_type, "category": r.category,
            "submitted_at": r.submitted_at.isoformat(), "age_days": age_days,
            "escalated": escalated,
            "verifier": verifiers[a.verifier_id].display_name if a and a.verifier_id in verifiers else None,
            "verifier_id": a.verifier_id if a else None,
        })
    rows.sort(key=lambda x: x["submitted_at"])
    return {"status": "ok", "counts": counts,
            "escalation_days": s.verification_escalation_days,
            "items": rows[:500]}


def list_verifiers(db: Session) -> list[dict]:
    out = []
    for u in db.execute(select(User).where(User.role.in_(["FACULTY", "VERIFIER"]))).scalars():
        cats = [c.category for c in db.execute(
            select(FacultyCategory).where(FacultyCategory.user_id == u.id)).scalars()]
        out.append({"id": u.id, "name": u.display_name, "email": u.email,
                    "categories": cats, "is_active": u.is_active})
    return out


def assign_verifiers(db: Session, tpo: User, request_ids: list[int], verifier_id: int) -> dict:
    v = db.get(User, verifier_id)
    if not v or v.role not in ("FACULTY", "VERIFIER"):
        raise HTTPException(400, "Verifier not found")
    v_cats = {c.category for c in db.execute(
        select(FacultyCategory).where(FacultyCategory.user_id == v.id)).scalars()}
    assigned, skipped = 0, 0
    for rid in request_ids:
        r = db.get(VerificationRequest, rid)
        if not r or r.status != "PENDING":
            skipped += 1
            continue
        if v_cats and r.category not in v_cats:
            skipped += 1
            continue
        a = db.execute(select(VerificationAssignment).where(
            VerificationAssignment.request_id == rid)).scalars().first()
        if a:
            a.verifier_id = v.id
            a.assigned_at = utcnow()
            a.status = "PENDING"
        else:
            db.add(VerificationAssignment(request_id=rid, verifier_id=v.id,
                                          assigned_by=tpo.id))
        assigned += 1
    db.commit()
    return {"assigned": assigned, "skipped": skipped}


# ---------------------------------------------------------------- departments
def list_departments(db: Session) -> list[dict]:
    depts = db.execute(select(Department).order_by(Department.code)).scalars().all()
    from app.models import Student, Prediction, PlacementCandidate
    out = []
    for d in depts:
        students = db.execute(select(Student).where(
            Student.is_active == True, Student.branch == d.code)).scalars().all()  # noqa: E712
        sids = {s.id for s in students}
        preds = [p for p in db.execute(select(Prediction).where(
            Prediction.is_current == True)).scalars() if p.student_id in sids]  # noqa: E712
        avg = round(sum(p.probability * 100 for p in preds) / len(preds), 1) if preds else None
        cands = [c for c in db.execute(select(PlacementCandidate)).scalars()
                 if c.student_id in sids]
        out.append({
            "code": d.code, "name": d.name, "students": len(students),
            "analyzed": len(preds), "average_readiness": avg,
            "ready_pct": round(sum(1 for p in preds if p.category == "READY") / len(preds) * 100, 0) if preds else None,
            "needs_training_pct": round(sum(1 for p in preds if p.category == "NEEDS_TRAINING") / len(preds) * 100, 0) if preds else None,
            "placed": sum(1 for c in cands if c.status == "PLACED"),
            "in_process": sum(1 for c in cands if c.status in
                              ("NOMINATED", "COMPANY_REVIEWING", "SHORTLISTED", "INTERVIEW", "SELECTED")),
        })
    return out
