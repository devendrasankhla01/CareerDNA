"""Verified Employability Passport (flagship differentiator A).

Owns the student-owned evidence lifecycle:
  submit  — create/update an evidence item + PENDING VerificationRequest
  resubmit — CORRECTION_REQUIRED -> PENDING (new review round)
  decide  — faculty approve / correct / reject (category-scoped, audited)

Trusted state: only status == VERIFIED rows count as verified evidence.
Every decision writes a VerificationReview audit row.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models import (
    Activity,
    Certification,
    FacultyCategory,
    Internship,
    OpenSource,
    Project,
    Skill,
    Student,
    StudentSkill,
    User,
    VerificationRequest,
    VerificationAssignment,
    VerificationReview,
)

ENTITY_MODELS = {
    "project": Project,
    "internship": Internship,
    "certification": Certification,
    "activity": Activity,
    "open_source": OpenSource,
    "skill": StudentSkill,
}

# category -> entity types it can verify
CATEGORY_ENTITIES = {
    "TECHNICAL_SKILL": {"skill"},
    "PROJECT": {"project"},
    "CERTIFICATION": {"certification"},
    "INTERNSHIP": {"internship"},
    "ACTIVITY": {"activity", "open_source"},
}

ENTITY_CATEGORY = {
    "skill": "TECHNICAL_SKILL",
    "project": "PROJECT",
    "certification": "CERTIFICATION",
    "internship": "INTERNSHIP",
    "activity": "ACTIVITY",
    "open_source": "ACTIVITY",
}

SOURCE_LABELS = {
    "INSTITUTION": "Institution",
    "ASSESSMENT": "Assessment",
    "FACULTY": "Faculty Verified",
    "SELF_REPORTED": "Self-reported",
}


def _entity_ref(db: Session, entity_type: str, entity_id: int):
    model = ENTITY_MODELS.get(entity_type)
    if not model:
        return None, None
    obj = db.get(model, entity_id)
    skill = None
    if entity_type == "skill" and obj:
        skill = db.get(Skill, obj.skill_id)
    return obj, skill


def _get_or_create_request(db: Session, student: Student, entity_type: str,
                           entity_id: int, resubmit: bool = False) -> VerificationRequest:
    req = db.execute(select(VerificationRequest).where(
        VerificationRequest.student_id == student.id,
        VerificationRequest.entity_type == entity_type,
        VerificationRequest.entity_id == entity_id)).scalars().first()
    if req is None:
        req = VerificationRequest(
            student_id=student.id, entity_type=entity_type, entity_id=entity_id,
            category=ENTITY_CATEGORY[entity_type], status="PENDING", resubmission=resubmit)
        db.add(req)
        db.flush()
        return req
    if req.status == "PENDING":
        if resubmit:
            req.resubmission = True
            req.updated_at = utcnow()
        return req
    if req.status == "VERIFIED":
        # editing verified evidence -> new review round
        req.status = "PENDING"
        req.resubmission = True
        req.updated_at = utcnow()
        return req
    if req.status == "CORRECTION_REQUIRED":
        req.status = "PENDING"
        req.resubmission = True
        req.updated_at = utcnow()
        return req
    if req.status == "REJECTED":
        # a rejected claim can start a fresh cycle with corrected data
        req.status = "PENDING"
        req.resubmission = True
        req.updated_at = utcnow()
        return req
    return req


def _write_review(db: Session, req: VerificationRequest, verifier: User,
                  previous: str, new_status: str, note: str | None) -> None:
    db.add(VerificationReview(
        request_id=req.id, verifier_id=verifier.id, previous_status=previous,
        new_status=new_status, note=note, reviewed_at=utcnow()))
    req.status = new_status
    req.updated_at = utcnow()


def _check_scope(user: User, db: Session, category: str, request_id: int | None = None) -> None:
    if user.role == "TPO_ADMIN":
        return
    if user.role not in ("FACULTY", "VERIFIER"):
        raise HTTPException(status_code=403, detail="Verifier access required")
    # A verifier may only act on requests ASSIGNED to them (TPO oversight).
    if request_id is not None:
        a = db.execute(select(VerificationAssignment).where(
            VerificationAssignment.request_id == request_id,
            VerificationAssignment.verifier_id == user.id,
            VerificationAssignment.status == "PENDING")).scalars().first()
        if not a:
            raise HTTPException(status_code=403,
                                detail="This verification request is not assigned to you.")
    cats = {c.category for c in db.execute(
        select(FacultyCategory).where(FacultyCategory.user_id == user.id)).scalars()}
    if cats and category not in cats:
        raise HTTPException(
            status_code=403,
            detail=f"You are not authorized to verify {category.replace('_', ' ').lower()} items.")


def _apply_decision_to_entity(db: Session, req: VerificationRequest, new_status: str,
                              corrections: dict | None, note: str | None) -> None:
    obj, skill = _entity_ref(db, req.entity_type, req.entity_id)
    if obj is None:
        req.status = "PENDING"
        return
    if req.entity_type == "skill":
        if new_status == "VERIFIED":
            if corrections and "score" in corrections:
                obj.score = float(corrections["score"])
            if corrections and corrections.get("source"):
                obj.source = corrections["source"]
            else:
                obj.source = "FACULTY"
            obj.status = "VERIFIED"
        elif new_status == "CORRECTION_REQUIRED":
            obj.status = "CORRECTION_REQUIRED"
        elif new_status == "REJECTED":
            obj.status = "REJECTED"
        obj.review_note = note
    else:
        if new_status == "VERIFIED":
            obj.status = "VERIFIED"
            if req.entity_type == "project" and corrections and corrections.get("complexity"):
                obj.verified_complexity = corrections["complexity"]
        elif new_status == "CORRECTION_REQUIRED":
            obj.status = "CORRECTION_REQUIRED"
        elif new_status == "REJECTED":
            obj.status = "REJECTED"
        obj.review_note = note


# ---------------------------------------------------------------- student side
def student_view_evidence(db: Session, student: Student) -> dict:
    def _state(obj, skill=None):
        req = db.execute(select(VerificationRequest).where(
            VerificationRequest.student_id == student.id,
            VerificationRequest.entity_type in (
                "skill" if skill else obj.__class__.__name__.lower()),
        )).scalars().first()
        return req.status if req else None

    out = {"skills": [], "projects": [], "internships": [], "certifications": [],
           "activities": [], "open_source": []}

    for ss in student.skills:
        out["skills"].append({
            "skill_code": ss.skill.code, "skill_name": ss.skill.name,
            "score": ss.score, "claimed_level": ss.claimed_level,
            "source": ss.source, "source_label": SOURCE_LABELS.get(ss.source, ss.source),
            "status": ss.status, "review_note": ss.review_note,
            "trust": "VERIFIED" if ss.status == "VERIFIED" else "UNVERIFIED",
        })
    for p in student.projects:
        out["projects"].append({
            "id": p.id, "title": p.title, "description": p.description,
            "tech_stack": p.tech_stack, "project_type": p.project_type,
            "team_type": p.team_type, "student_role": p.student_role,
            "claimed_complexity": p.claimed_complexity,
            "verified_complexity": p.verified_complexity,
            "github_url": p.github_url, "demo_url": p.demo_url,
            "completion_date": p.completion_date,
            "status": p.status, "review_note": p.review_note,
        })
    for i in student.internships:
        out["internships"].append({
            "id": i.id, "organization": i.organization, "role": i.role,
            "domain": i.domain, "start_date": i.start_date, "end_date": i.end_date,
            "description": i.description, "status": i.status, "review_note": i.review_note,
        })
    for c in student.certifications:
        out["certifications"].append({
            "id": c.id, "name": c.name, "issuer": c.issuer,
            "credential_id": c.credential_id, "credential_url": c.credential_url,
            "issue_date": c.issue_date, "expiry_date": c.expiry_date,
            "skill_category": c.skill_category, "status": c.status, "review_note": c.review_note,
        })
    for a in student.activities:
        out["activities"].append({
            "id": a.id, "event_name": a.event_name, "event_type": a.event_type,
            "organizer": a.organizer, "event_date": a.event_date, "role": a.role,
            "achievement": a.achievement, "status": a.status, "review_note": a.review_note,
        })
    for o in student.open_sources:
        out["open_source"].append({
            "id": o.id, "repository_url": o.repository_url,
            "contribution_type": o.contribution_type, "description": o.description,
            "status": o.status, "review_note": o.review_note,
        })

    # passport states
    all_items = (out["skills"] + out["projects"] + out["internships"]
                 + out["certifications"] + out["activities"] + out["open_source"])
    counts = {"PENDING": 0, "VERIFIED": 0, "CORRECTION_REQUIRED": 0, "REJECTED": 0, "NONE": 0}
    for item in all_items:
        counts[item.get("status") or "NONE"] = counts.get(item.get("status") or "NONE", 0) + 1
    pending = counts.get("PENDING", 0)
    verified = counts.get("VERIFIED", 0)
    correction = counts.get("CORRECTION_REQUIRED", 0)
    rejected = counts.get("REJECTED", 0)
    if correction:
        passport_state = "CORRECTION_REQUIRED"
    elif pending:
        passport_state = "PENDING"
    elif verified:
        passport_state = "VERIFIED"
    elif rejected:
        passport_state = "REJECTED"
    else:
        passport_state = "NONE"
    out["passport"] = {
        "state": passport_state,
        "counts": counts,
        "note": ("Some items need correction or review" if correction
                 else "All submitted items have a review decision" if (verified or rejected) and not pending
                 else "Awaiting faculty verification"),
    }
    return out


def _request_for(db: Session, student: Student, entity_type: str, entity_id: int) -> VerificationRequest | None:
    return db.execute(select(VerificationRequest).where(
        VerificationRequest.student_id == student.id,
        VerificationRequest.entity_type == entity_type,
        VerificationRequest.entity_id == entity_id)).scalars().first()


# ---------------------------------------------------------------- faculty side
def faculty_queue(db: Session, user: User, category: str | None = None,
                  status: str = "PENDING", page: int = 1, page_size: int = 15) -> dict:
    if user.role == "FACULTY":
        cats = {c.category for c in db.execute(
            select(FacultyCategory).where(FacultyCategory.user_id == user.id)).scalars()}
        if not cats:
            return {"status": "ok", "total": 0, "page": page, "page_size": page_size, "items": []}
        if category:
            if category not in cats:
                raise HTTPException(status_code=403, detail="Not in your verification category")
            cat_filter = [category]
        else:
            cat_filter = list(cats)
    else:
        cat_filter = [category] if category else None

    conds = [VerificationRequest.status == status]
    if cat_filter:
        conds.append(VerificationRequest.category.in_(cat_filter))
    # Verifiers (faculty) see ONLY requests the TPO assigned to them.
    if user.role in ("FACULTY", "VERIFIER"):
        assigned = select(VerificationAssignment.request_id).where(
            VerificationAssignment.verifier_id == user.id,
            VerificationAssignment.status == "PENDING")
        conds.append(VerificationRequest.id.in_(assigned))
    total = db.execute(
        select(VerificationRequest).where(*conds)
    ).scalars().all()
    items = []
    for req in total:
        st = db.get(Student, req.student_id)
        if not st:
            continue
        obj, skill = _entity_ref(db, req.entity_type, req.entity_id)
        if obj is None:
            continue
        items.append({
            "request_id": req.id,
            "student_id": st.id,
            "student_name": st.user.display_name if st.user else st.usn,
            "usn": st.usn, "branch": st.branch, "semester": st.semester,
            "entity_type": req.entity_type, "entity_id": req.entity_id,
            "category": req.category, "status": req.status,
            "resubmission": req.resubmission,
            "submitted_at": req.submitted_at.isoformat(),
            "updated_at": req.updated_at.isoformat(),
            "summary": _item_summary(req.entity_type, obj, skill),
            "last_review": _last_review(db, req),
        })
    items.sort(key=lambda r: r["submitted_at"])
    start = (page - 1) * page_size
    return {"status": "ok", "total": len(items), "page": page,
            "page_size": page_size, "items": items[start:start + page_size]}


def _item_summary(entity_type: str, obj, skill) -> dict:
    if entity_type == "skill" and skill:
        return {"name": skill.name, "code": skill.code, "score": obj.score,
                "claimed_level": obj.claimed_level, "source": obj.source,
                "source_label": SOURCE_LABELS.get(obj.source, obj.source)}
    if entity_type == "project":
        return {"name": obj.title, "student_role": obj.student_role,
                "claimed_complexity": obj.claimed_complexity,
                "tech_stack": obj.tech_stack, "completion_date": obj.completion_date,
                "github_url": obj.github_url, "demo_url": obj.demo_url,
                "description": obj.description}
    if entity_type == "internship":
        return {"name": obj.organization, "role": obj.role, "domain": obj.domain,
                "start_date": obj.start_date, "end_date": obj.end_date,
                "description": obj.description}
    if entity_type == "certification":
        return {"name": obj.name, "issuer": obj.issuer, "credential_id": obj.credential_id,
                "credential_url": obj.credential_url, "issue_date": obj.issue_date,
                "skill_category": obj.skill_category}
    if entity_type == "activity":
        return {"name": obj.event_name, "event_type": obj.event_type,
                "organizer": obj.organizer, "event_date": obj.event_date,
                "role": obj.role, "achievement": obj.achievement}
    if entity_type == "open_source":
        return {"name": obj.repository_url, "contribution_type": obj.contribution_type,
                "description": obj.description}
    return {}


def _last_review(db: Session, req: VerificationRequest):
    reviews = db.execute(select(VerificationReview).where(
        VerificationReview.request_id == req.id).order_by(VerificationReview.reviewed_at.desc())
    ).scalars().first()
    if not reviews:
        return None
    v = db.get(User, reviews.verifier_id)
    return {"verifier": v.display_name if v else "unknown",
            "status": reviews.new_status, "note": reviews.note,
            "at": reviews.reviewed_at.isoformat()}


def faculty_detail(db: Session, user: User, request_id: int) -> dict:
    req = db.get(VerificationRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _check_scope(user, db, req.category, request_id=request_id)
    st = db.get(Student, req.student_id)
    obj, skill = _entity_ref(db, req.entity_type, req.entity_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Evidence item no longer exists")

    # related verified evidence context (passport)
    related = db.execute(select(VerificationRequest).where(
        VerificationRequest.student_id == st.id,
        VerificationRequest.entity_id != req.entity_id)).scalars().all()
    history = [{"verifier": (db.get(User, r.verifier_id).display_name if db.get(User, r.verifier_id) else "unknown"),
                "previous_status": r.previous_status, "new_status": r.new_status,
                "note": r.note, "at": r.reviewed_at.isoformat()}
               for r in db.execute(select(VerificationReview).where(
                   VerificationReview.request_id == req.id)
                   .order_by(VerificationReview.reviewed_at.asc())).scalars()]
    return {
        "status": "ok",
        "request": {"id": req.id, "student_id": st.id,
                    "student_name": st.user.display_name if st.user else st.usn,
                    "usn": st.usn, "branch": st.branch, "semester": st.semester,
                    "entity_type": req.entity_type, "entity_id": req.entity_id,
                    "category": req.category, "status": req.status,
                    "resubmission": req.resubmission,
                    "submitted_at": req.submitted_at.isoformat()},
        "item": _item_summary(req.entity_type, obj, skill),
        "history": history,
        "student_verified_count": sum(
            1 for r in related if r.status == "VERIFIED"),
        "student_pending_count": sum(1 for r in related if r.status == "PENDING"),
    }


def faculty_decide(db: Session, user: User, request_id: int, decision: str,
                   note: str | None = None, corrections: dict | None = None) -> dict:
    req = db.get(VerificationRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    _check_scope(user, db, req.category, request_id=request_id)
    if req.status != "PENDING":
        raise HTTPException(status_code=409, detail="Request already reviewed")
    if decision not in ("VERIFIED", "CORRECTION_REQUIRED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Invalid decision")
    if decision == "CORRECTION_REQUIRED" and not (note or "").strip():
        raise HTTPException(status_code=400, detail="Correction note is required")
    if decision == "REJECTED" and not (note or "").strip():
        raise HTTPException(status_code=400, detail="Rejection note is required")

    previous = req.status
    _write_review(db, req, user, previous, decision, note)
    _apply_decision_to_entity(db, req, decision, corrections, note)
    db.flush()

    # recompute prediction if trust-relevant entity changed
    from app.services.analysis_service import get_current_prediction, run_analysis
    st = db.get(Student, req.student_id)
    if st and decision in ("VERIFIED", "REJECTED", "CORRECTION_REQUIRED"):
        # supersede + recompute if the student already has an analysis
        if get_current_prediction(db, st) is not None:
            run_analysis(db, st, reason=f"verification_{decision.lower()}")

    db.commit()
    return {"status": "ok", "request_id": request_id, "decision": decision}


# ---------------------------------------------------------------- submit (student)
def submit_item(db: Session, student: Student, entity_type: str, payload: dict) -> dict:
    """Create or update a student-owned evidence item and queue it for review."""
    if entity_type not in ENTITY_MODELS:
        raise HTTPException(status_code=400, detail="Unknown entity type")
    model = ENTITY_MODELS[entity_type]

    obj_id = payload.get("id")
    obj = None
    if obj_id:
        obj = db.get(model, int(obj_id))
        if not obj or obj.student_id != student.id:
            raise HTTPException(status_code=404, detail="Item not found")
    if obj is None:
        obj = model(student_id=student.id)
        db.add(obj)
    for k, v in _fields_for(entity_type, payload).items():
        setattr(obj, k, v)
    if entity_type != "skill":
        db.flush()  # skill rows need skill_id assigned first (handled below)

    if entity_type == "skill":
        skill_code = payload.get("skill_code")
        skill = db.execute(select(Skill).where(Skill.code == skill_code)).scalars().first()
        if not skill:
            raise HTTPException(status_code=400, detail="Unknown skill")
        # skill rows are upserted by (student, skill)
        existing = db.execute(select(StudentSkill).where(
            StudentSkill.student_id == student.id, StudentSkill.skill_id == skill.id)).scalars().first()
        if existing is not None and existing.id != obj.id:
            if existing.status == "VERIFIED" and existing.source in ("ASSESSMENT", "INSTITUTION"):
                raise HTTPException(status_code=409,
                                    detail="This assessment is institution-verified and cannot be self-modified")
            db.delete(obj)
            obj = existing
        obj.skill_id = skill.id
        obj.claimed_level = payload.get("claimed_level")
        if existing is None:
            obj.source = "SELF_REPORTED"
            obj.status = "PENDING"
        else:
            obj.status = "PENDING"
            if obj.source not in ("ASSESSMENT", "INSTITUTION"):
                obj.source = "SELF_REPORTED"
        db.flush()
        _get_or_create_request(db, student, "skill", obj.id, resubmit=existing is not None)
    else:
        _get_or_create_request(db, student, entity_type, obj.id, resubmit=obj_id is not None)

    db.commit()
    return {"status": "ok", "entity_type": entity_type, "entity_id": obj.id}


def _fields_for(entity_type: str, payload: dict) -> dict:
    allowed = {
        "project": ["title", "description", "tech_stack", "project_type", "team_type",
                    "student_role", "claimed_complexity", "github_url", "demo_url", "completion_date"],
        "internship": ["organization", "role", "domain", "start_date", "end_date", "description"],
        "certification": ["name", "issuer", "credential_id", "credential_url",
                          "issue_date", "expiry_date", "skill_category"],
        "activity": ["event_name", "event_type", "organizer", "event_date", "role", "achievement"],
        "open_source": ["repository_url", "contribution_type", "description"],
        "skill": [],
    }
    return {k: payload[k] for k in allowed.get(entity_type, []) if payload.get(k) is not None}


def resubmit(db: Session, student: Student, entity_type: str, entity_id: int,
             payload: dict | None = None) -> dict:
    req = _request_for(db, student, entity_type, entity_id)
    if not req:
        raise HTTPException(status_code=404, detail="No verification request for this item")
    if req.status not in ("CORRECTION_REQUIRED", "REJECTED"):
        raise HTTPException(status_code=409, detail="Item is not awaiting correction")
    return submit_item(db, student, entity_type, {"id": entity_id, **(payload or {})})
