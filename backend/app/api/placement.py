"""Placement management APIs — four dashboards + verifier.

Authorization is enforced here (backend), not in the UI:
  * STUDENT   -> own data only
  * DEPARTMENT-> own department only (scope applied in dept_service)
  * TPO_ADMIN -> institution-wide
  * COMPANY   -> only own drives + TPO-nominated candidates (never INTERESTED)
  * VERIFIER  -> only assigned verification requests
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import PlacementCandidate, PlacementDrive, Student, User
from app.services import dept_service, matching_service, placement_service, placement_admin_service
from app.services.auth_service import (
    require_company,
    require_department,
    require_student,
    require_tpo,
)

router = APIRouter(prefix="/api", tags=["placement"])


# ================================================================== STUDENT
@router.get("/student/companies")
def student_companies(db: Session = Depends(get_db), user: User = Depends(require_student)):
    st = db.execute(select(Student).where(Student.user_id == user.id)).scalars().first()
    if not st:
        raise HTTPException(404, "Student profile not found")
    if st.available_for_placement is False:
        return {"status": "ok", "opportunities": [], "message":
                "Your profile is currently not marked as available for placements."}
    opps = matching_service.matches_for_student(db, st)
    top = [o for o in opps if o["eligible"]][:3]
    return {"status": "ok", "opportunities": opps, "best_opportunities": top}


@router.get("/student/companies/{drive_id}")
def student_company_detail(drive_id: int, db: Session = Depends(get_db),
                           user: User = Depends(require_student)):
    st = db.execute(select(Student).where(Student.user_id == user.id)).scalars().first()
    if not st:
        raise HTTPException(404, "Student profile not found")
    drive = db.get(PlacementDrive, drive_id)
    if not drive or drive.status != "OPEN":
        raise HTTPException(404, "Drive not open")
    inp = matching_service._load_inputs(db).get(st.id, {})
    r = matching_service.evaluate_one(drive, st, inp, get_settings().company_match_weights)
    if r is None:
        raise HTTPException(409, "Profile is not analyzed yet")
    c = placement_service.get_candidate(db, drive_id, st.id)
    return {"status": "ok", "candidate_status": c.status if c else None, **r,
            **matching_service._drive_public(db, drive)}


@router.post("/student/companies/{drive_id}/interest")
def student_express_interest(drive_id: int, db: Session = Depends(get_db),
                             user: User = Depends(require_student)):
    placement_service.express_interest(db, user, drive_id)
    return {"status": "ok", "message": "Interest recorded. The TPO reviews and nominates."}


@router.get("/student/placement-journey")
def student_journey(db: Session = Depends(get_db), user: User = Depends(require_student)):
    st = db.execute(select(Student).where(Student.user_id == user.id)).scalars().first()
    if not st:
        raise HTTPException(404, "Student profile not found")
    journey = placement_service.student_journey(db, st)
    current = journey[0]["status"] if journey else None
    return {"status": "ok", "journey": journey, "current_stage": current}


# ================================================================== TPO
class CompanyIn(BaseModel):
    name: str
    industry: str | None = None
    website: str | None = None
    description: str | None = None
    location: str | None = None
    status: str = "ACTIVE"
    recruiter_email: str | None = None
    recruiter_password: str | None = None
    recruiter_name: str | None = None


class DriveIn(BaseModel):
    company_id: int | None = None
    title: str
    role: str
    job_description: str | None = None
    location: str | None = None
    ctc: str | None = None
    employment_type: str | None = None
    drive_date: str | None = None
    deadline: str | None = None
    open_positions: int | None = None
    min_cgpa: float | None = None
    min_tenth: float | None = None
    min_twelfth: float | None = None
    max_backlogs: int | None = None
    min_readiness: float | None = None
    min_coding: float | None = None
    min_aptitude: float | None = None
    min_communication: float | None = None
    project_required: bool = False
    internship_required: bool = False
    target_branches: list[str] | None = None
    eligible_semesters: list[int] | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    preferred_career_code: str | None = None
    status: str = "DRAFT"


@router.get("/tpo/companies")
def tpo_companies(db: Session = Depends(get_db), user: User = Depends(require_tpo)):
    return placement_admin_service.list_companies(db)


@router.post("/tpo/companies")
def tpo_create_company(data: CompanyIn, db: Session = Depends(get_db),
                       user: User = Depends(require_tpo)):
    c = placement_admin_service.create_company(db, user, data.model_dump())
    return {"status": "ok", "id": c.id, "name": c.name}


@router.put("/tpo/companies/{company_id}")
def tpo_update_company(company_id: int, data: dict, db: Session = Depends(get_db),
                       user: User = Depends(require_tpo)):
    c = placement_admin_service.update_company(db, user, company_id, data)
    return {"status": "ok", "id": c.id, "name": c.name}


@router.get("/tpo/drives")
def tpo_drives(company_id: int | None = None, db: Session = Depends(get_db),
               user: User = Depends(require_tpo)):
    return placement_admin_service.list_drives(db, company_id)


@router.post("/tpo/drives")
def tpo_create_drive(data: DriveIn, db: Session = Depends(get_db),
                     user: User = Depends(require_tpo)):
    d = placement_admin_service.create_drive(db, user, data.model_dump())
    return {"status": "ok", "id": d.id, "title": d.title, "criteria_version": d.criteria_version}


@router.put("/tpo/drives/{drive_id}")
def tpo_update_drive(drive_id: int, data: dict, db: Session = Depends(get_db),
                     user: User = Depends(require_tpo)):
    d = placement_admin_service.update_drive(db, user, drive_id, data)
    return {"status": "ok", "id": d.id, "criteria_version": d.criteria_version}


@router.post("/tpo/drives/{drive_id}/status")
def tpo_drive_status(drive_id: int, data: dict, db: Session = Depends(get_db),
                     user: User = Depends(require_tpo)):
    d = placement_admin_service.set_drive_status(db, user, drive_id, data.get("status", "OPEN"))
    return {"status": "ok", "drive_status": d.status}


@router.get("/tpo/matching/drives/{drive_id}")
def tpo_drive_matching(drive_id: int, include_ineligible: bool = True,
                       only_almost: bool = False,
                       db: Session = Depends(get_db),
                       user: User = Depends(require_tpo)):
    drive = db.get(PlacementDrive, drive_id)
    if not drive:
        raise HTTPException(404, "Drive not found")
    students = {s.id: s for s in db.execute(
        select(Student).where(Student.is_active == True)).scalars()}  # noqa: E712
    matches = matching_service.matches_for_drive(db, drive, set(students))
    if not include_ineligible:
        matches = [m for m in matches if m["eligible"]]
    if only_almost:
        matches = [m for m in matches if m["almost_eligible"]]
    cands = {c.student_id: c for c in db.execute(
        select(PlacementCandidate).where(PlacementCandidate.drive_id == drive_id)).scalars()}
    for m in matches:
        c = cands.get(m["student_id"])
        m["candidate_status"] = c.status if c else None
    pipeline = placement_service.drive_pipeline(db, drive, set(students))
    weights = get_settings().company_match_weights
    return {"status": "ok", "drive": matching_service._drive_public(db, drive),
            "weights": weights, "components": matching_service.COMPONENT_LABELS,
            "candidates": matches, "pipeline": pipeline}


class NominateIn(BaseModel):
    student_ids: list[int]
    note: str | None = None


@router.post("/tpo/matching/drives/{drive_id}/nominate")
def tpo_nominate(drive_id: int, data: NominateIn, db: Session = Depends(get_db),
                 user: User = Depends(require_tpo)):
    result = placement_service.nominate(db, user, drive_id, data.student_ids, data.note)
    return {"status": "ok", **result}


@router.get("/tpo/verification-center")
def tpo_verification_center(status: str | None = None, department: str | None = None,
                            category: str | None = None, verifier: int | None = None,
                            db: Session = Depends(get_db),
                            user: User = Depends(require_tpo)):
    return placement_admin_service.verification_center(
        db, {"status": status, "department": department, "category": category,
             "verifier": verifier})


@router.get("/tpo/verifiers")
def tpo_verifiers(db: Session = Depends(get_db), user: User = Depends(require_tpo)):
    return {"status": "ok", "verifiers": placement_admin_service.list_verifiers(db)}


class AssignIn(BaseModel):
    request_ids: list[int]
    verifier_id: int


@router.post("/tpo/verification-center/assign")
def tpo_assign(data: AssignIn, db: Session = Depends(get_db),
               user: User = Depends(require_tpo)):
    return {"status": "ok", **placement_admin_service.assign_verifiers(
        db, user, data.request_ids, data.verifier_id)}


@router.get("/tpo/departments")
def tpo_departments(db: Session = Depends(get_db), user: User = Depends(require_tpo)):
    return {"status": "ok", "departments": placement_admin_service.list_departments(db)}


@router.get("/tpo/placements")
def tpo_placements(db: Session = Depends(get_db), user: User = Depends(require_tpo)):
    return {"status": "ok", **placement_service.placements_list(db)}


@router.post("/tpo/placements/{candidate_id}/confirm")
def tpo_confirm(candidate_id: int, data: dict | None = None,
                db: Session = Depends(get_db), user: User = Depends(require_tpo)):
    c = placement_service.confirm_placement(db, user, candidate_id, (data or {}).get("note"))
    return {"status": "ok", "message": "Placement confirmed by TPO", "status": c.status}


class AvailabilityIn(BaseModel):
    available: bool
    reason: str | None = None


@router.post("/tpo/students/{student_id}/availability")
def tpo_student_availability(student_id: int, data: AvailabilityIn,
                             db: Session = Depends(get_db),
                             user: User = Depends(require_tpo)):
    st = db.get(Student, student_id)
    if not st:
        raise HTTPException(404, "Student not found")
    st.available_for_placement = data.available
    db.commit()
    return {"status": "ok", "available_for_placement": st.available_for_placement}


# ================================================================== DEPARTMENT
@router.get("/dept/overview")
def dept_overview(db: Session = Depends(get_db), user: User = Depends(require_department)):
    return dept_service.overview(db, user.department.code)


@router.get("/dept/skills")
def dept_skills(db: Session = Depends(get_db), user: User = Depends(require_department)):
    return dept_service.skill_gaps(db, user.department.code)


@router.get("/dept/performance")
def dept_performance(db: Session = Depends(get_db), user: User = Depends(require_department)):
    return dept_service.performance(db, user.department.code)


@router.get("/dept/companies")
def dept_companies(db: Session = Depends(get_db), user: User = Depends(require_department)):
    return dept_service.company_eligibility(db, user.department.code)


@router.get("/dept/placements")
def dept_placements(db: Session = Depends(get_db), user: User = Depends(require_department)):
    return dept_service.placement_status(db, user.department.code)


class DeptUpdateIn(BaseModel):
    updates: dict


@router.post("/dept/students/{student_id}")
def dept_update_student(student_id: int, data: DeptUpdateIn,
                        db: Session = Depends(get_db),
                        user: User = Depends(require_department)):
    return dept_service.update_student(db, user, student_id, data.updates)


class DeptBulkIn(BaseModel):
    rows: list[dict]


@router.post("/dept/bulk")
def dept_bulk(rows: DeptBulkIn, db: Session = Depends(get_db),
              user: User = Depends(require_department)):
    return dept_service.bulk_update(db, user, rows.rows)


# ================================================================== COMPANY
@router.get("/company/overview")
def company_overview(db: Session = Depends(get_db), user: User = Depends(require_company)):
    if not user.company_id:
        raise HTTPException(403, "Company account not linked")
    drives = db.execute(select(PlacementDrive).where(
        PlacementDrive.company_id == user.company_id)).scalars().all()
    drive_ids = [d.id for d in drives]
    cands = db.execute(select(PlacementCandidate).where(
        PlacementCandidate.drive_id.in_(drive_ids))).scalars().all() if drive_ids else []
    from collections import Counter
    st = Counter(c.status for c in cands)
    open_drives = [d for d in drives if d.status == "OPEN"]
    pipeline = {}
    for d in open_drives:
        pipeline[d.id] = placement_service.drive_pipeline(db, d)
    return {"status": "ok", "company": {"id": user.company_id, "name": user.company.name},
            "open_drives": len(open_drives), "total_drives": len(drives),
            "candidates": {
                "nominated": st.get("NOMINATED", 0) + st.get("COMPANY_REVIEWING", 0),
                "shortlisted": st.get("SHORTLISTED", 0),
                "interview": st.get("INTERVIEW", 0),
                "selected": st.get("SELECTED", 0),
                "placed": st.get("PLACED", 0),
                "not_selected": st.get("NOT_SELECTED", 0),
            },
            "open_pipeline": pipeline}


@router.get("/company/drives")
def company_drives(db: Session = Depends(get_db), user: User = Depends(require_company)):
    if not user.company_id:
        raise HTTPException(403, "Company account not linked")
    drives = db.execute(select(PlacementDrive).where(
        PlacementDrive.company_id == user.company_id)).scalars().all()
    out = []
    for d in drives:
        cands = db.execute(select(PlacementCandidate).where(
            PlacementCandidate.drive_id == d.id)).scalars().all()
        visible = [c for c in cands if c.status != "INTERESTED"]
        out.append({
            "id": d.id, "title": d.title, "role": d.role, "status": d.status,
            "location": d.location, "ctc": d.ctc, "drive_date": d.drive_date,
            "deadline": d.deadline, "open_positions": d.open_positions,
            "criteria": {
                "min_cgpa": d.min_cgpa, "min_tenth": d.min_tenth,
                "min_twelfth": d.min_twelfth, "max_backlogs": d.max_backlogs,
                "min_readiness": d.min_readiness, "min_coding": d.min_coding,
                "min_aptitude": d.min_aptitude, "min_communication": d.min_communication,
                "project_required": d.project_required, "internship_required": d.internship_required,
                "target_branches": d.target_branches, "eligible_semesters": d.eligible_semesters,
                "required_skills": d.required_skills, "preferred_skills": d.preferred_skills,
            },
            "counts": {
                "nominated": sum(1 for c in visible if c.status in ("NOMINATED", "COMPANY_REVIEWING")),
                "shortlisted": sum(1 for c in visible if c.status in ("SHORTLISTED",)),
                "interview": sum(1 for c in visible if c.status in ("INTERVIEW",)),
                "selected": sum(1 for c in visible if c.status in ("SELECTED", "PLACED")),
            },
        })
    return {"status": "ok", "drives": out}


@router.get("/company/drives/{drive_id}/candidates")
def company_drive_candidates(drive_id: int, tab: str | None = None,
                             db: Session = Depends(get_db),
                             user: User = Depends(require_company)):
    drive = db.get(PlacementDrive, drive_id)
    if not drive or drive.company_id != user.company_id:
        raise HTTPException(403, "Drive not authorized for your company")
    cands = db.execute(select(PlacementCandidate).where(
        PlacementCandidate.drive_id == drive_id)).scalars().all()
    # company sees TPO-nominated and beyond — never INTERESTED
    cands = [c for c in cands if c.status != "INTERESTED"]
    tabs = {"NOMINATED": ("NOMINATED", "COMPANY_REVIEWING"), "SHORTLISTED": ("SHORTLISTED",),
            "INTERVIEW": ("INTERVIEW",), "SELECTED": ("SELECTED", "PLACED"),
            "NOT_SELECTED": ("NOT_SELECTED",)}
    if tab and tab in tabs:
        cands = [c for c in cands if c.status in tabs[tab]]
    inp = matching_service._load_inputs(db)
    weights = get_settings().company_match_weights
    rows = []
    for c in sorted(cands, key=lambda x: -x.updated_at.timestamp()):
        st = db.get(Student, c.student_id)
        if not st:
            continue
        i = inp.get(st.id, {})
        r = matching_service.evaluate_one(drive, st, i, weights)
        rows.append({
            "student_id": st.id,
            "name": st.user.display_name if st.user else st.usn,
            "usn": st.usn, "branch": st.branch, "semester": st.semester,
            "cgpa": i.get("cgpa"), "readiness": i.get("readiness"),
            "category": i.get("category"),
            "company_match": r["match_score"] if r else None,
            "eligible": r["eligible"] if r else None,
            "career_best": max(i.get("career", {}).items(), key=lambda kv: kv[1], default=(None, 0))[0],
            "top_skills": [matching_service.SKILL_LABELS.get(c2, c2) for c2 in
                           (drive.required_skills or []) + (drive.preferred_skills or [])
                           if i.get("skills", {}).get(c2, 0) >= 60][:5],
            "status": c.status,
            "match_score": c.match_score,
            "updated_at": c.updated_at.isoformat(),
        })
    rows.sort(key=lambda x: (-int(x["eligible"] or 0), -(x["company_match"] or 0)))
    return {"status": "ok", "drive_id": drive_id, "role": drive.role, "rows": rows,
            "tabs": {k: sum(1 for c in cands if c.status in v)
                     for k, v in {
                         "NOMINATED": ("NOMINATED", "COMPANY_REVIEWING"),
                         "SHORTLISTED": ("SHORTLISTED",),
                         "INTERVIEW": ("INTERVIEW",),
                         "SELECTED": ("SELECTED", "PLACED"),
                         "NOT_SELECTED": ("NOT_SELECTED",)}.items()}}


class CompanyStatusIn(BaseModel):
    status: str
    note: str | None = None


@router.post("/company/drives/{drive_id}/candidates/{student_id}/status")
def company_candidate_status(drive_id: int, student_id: int, data: CompanyStatusIn,
                             db: Session = Depends(get_db),
                             user: User = Depends(require_company)):
    c = placement_service.company_transition(db, user, drive_id, student_id,
                                              data.status, data.note)
    return {"status": "ok", "candidate_status": c.status}


@router.get("/company/drives/{drive_id}/candidates/{student_id}")
def company_candidate_detail(drive_id: int, student_id: int,
                             db: Session = Depends(get_db),
                             user: User = Depends(require_company)):
    return placement_service.company_candidate_detail(db, user, drive_id, student_id)


@router.get("/company/selections")
def company_selections(db: Session = Depends(get_db), user: User = Depends(require_company)):
    if not user.company_id:
        raise HTTPException(403, "Company account not linked")
    drives = db.execute(select(PlacementDrive).where(
        PlacementDrive.company_id == user.company_id)).scalars().all()
    rows = []
    for d in drives:
        cands = db.execute(select(PlacementCandidate).where(
            PlacementCandidate.drive_id == d.id)).scalars().all()
        for c in cands:
            if c.status in ("SELECTED", "PLACED", "NOT_SELECTED"):
                st = db.get(Student, c.student_id)
                rows.append({
                    "drive": d.title, "role": d.role,
                    "name": st.user.display_name if st and st.user else None,
                    "usn": st.usn if st else None, "branch": st.branch if st else None,
                    "status": c.status,
                    "selected_at": c.selected_at.isoformat() if c.selected_at else None,
                    "confirmed": c.status == "PLACED",
                    "confirmed_at": c.confirmed_at.isoformat() if c.confirmed_at else None,
                })
    rows.sort(key=lambda r: r["selected_at"] or "", reverse=True)
    return {"status": "ok", "rows": rows}
