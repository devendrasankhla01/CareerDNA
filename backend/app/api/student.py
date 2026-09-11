from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import Skill, Student
from app.schemas import (
    ActivityIn, CertificationIn, InternshipIn, OpenSourceIn, ProjectIn,
    RoadmapIn, RoadmapItemStatusIn, SimulateIn, SkillClaimIn, TargetCareerIn,
)
from app.services import (
    analysis_service,
    auth_service,
    career_service,
    optimizer_service,
    profile_service,
    roadmap_service,
    verification_service,
)
from app.services.auth_service import get_current_user, get_student_for_user
from app.services.model_service import model_service

router = APIRouter(prefix="/api/student", tags=["student"])


def _student(user=Depends(auth_service.require_student),
             db: Session = Depends(get_db)) -> Student:
    return get_student_for_user(db, user)


# ---------------------------------------------------------------- readiness
@router.get("/readiness")
def readiness(s: Student = Depends(_student), db: Session = Depends(get_db)):
    if not model_service.available:
        return {"status": "model_unavailable",
                "message": "The readiness model is not deployed yet. Run scripts/train_model.py."}
    return analysis_service.analysis_payload(db, s)


@router.post("/readiness/refresh")
def refresh(s: Student = Depends(_student), db: Session = Depends(get_db)):
    if not model_service.available:
        return {"status": "model_unavailable"}
    pred = analysis_service.run_analysis(db, s, reason="manual_refresh")
    return {"status": "ok", "prediction_id": pred.id if pred else None}


# ---------------------------------------------------------------- profile
@router.get("/profile")
def profile(s: Student = Depends(_student), db: Session = Depends(get_db)):
    prof = profile_service.profile_summary(db, s)
    academic = s.academic
    return {
        "status": "ok",
        "academic": {
            "cgpa": academic.cgpa if academic else None,
            "tenth_percentage": academic.tenth_percentage if academic else None,
            "twelfth_percentage": academic.twelfth_percentage if academic else None,
            "backlog_history_count": academic.backlog_history_count if academic else None,
            "source": "INSTITUTION",
            "source_label": "Institution",
            "editable": False,
        } if academic else None,
        "features": prof["features"],
        "trust": prof["trust"],
        "completeness": prof["completeness"],
        "eligibility": prof["eligibility"],
        "flags": {
            "no_projects_declared": s.no_projects_declared,
            "no_internships_declared": s.no_internships_declared,
            "no_certifications_declared": s.no_certifications_declared,
            "no_activities_declared": s.no_activities_declared,
        },
    }


@router.get("/passport")
def passport(s: Student = Depends(_student), db: Session = Depends(get_db)):
    data = verification_service.student_view_evidence(db, s)
    prof = profile_service.profile_summary(db, s)
    data["trust"] = prof["trust"]
    data["completeness"] = prof["completeness"]
    return data


# ---------------------------------------------------------------- evidence CRUD
@router.post("/skills/claim")
def claim_skill(body: SkillClaimIn, s: Student = Depends(_student), db: Session = Depends(get_db)):
    return verification_service.submit_item(db, s, "skill", body.model_dump())


@router.post("/projects")
def upsert_project(body: ProjectIn, s: Student = Depends(_student), db: Session = Depends(get_db)):
    return verification_service.submit_item(db, s, "project", body.model_dump())


@router.post("/internships")
def upsert_internship(body: InternshipIn, s: Student = Depends(_student), db: Session = Depends(get_db)):
    return verification_service.submit_item(db, s, "internship", body.model_dump())


@router.post("/certifications")
def upsert_certification(body: CertificationIn, s: Student = Depends(_student), db: Session = Depends(get_db)):
    return verification_service.submit_item(db, s, "certification", body.model_dump())


@router.post("/activities")
def upsert_activity(body: ActivityIn, s: Student = Depends(_student), db: Session = Depends(get_db)):
    return verification_service.submit_item(db, s, "activity", body.model_dump())


@router.post("/open-source")
def upsert_open_source(body: OpenSourceIn, s: Student = Depends(_student), db: Session = Depends(get_db)):
    return verification_service.submit_item(db, s, "open_source", body.model_dump())


@router.post("/evidence/resubmit/{entity_type}/{entity_id}")
def resubmit(entity_type: str, entity_id: int, s: Student = Depends(_student),
             db: Session = Depends(get_db)):
    return verification_service.resubmit(db, s, entity_type, entity_id)


# ---------------------------------------------------------------- evidence files
ALLOWED_MIME = {"application/pdf", "image/png", "image/jpeg"}


@router.post("/evidence/files/{entity_type}/{entity_id}")
async def upload_evidence(entity_type: str, entity_id: int,
                          file: UploadFile = File(...),
                          s: Student = Depends(_student), db: Session = Depends(get_db)):
    from app.models import EvidenceFile
    from app.services.verification_service import ENTITY_MODELS

    model = ENTITY_MODELS.get(entity_type)
    if not model:
        raise HTTPException(status_code=400, detail="Unknown entity type")
    obj = db.get(model, entity_id)
    if not obj or obj.student_id != s.id:
        raise HTTPException(status_code=404, detail="Item not found")

    s_settings = get_settings()
    max_bytes = int(s_settings.max_upload_mb * 1024 * 1024)
    data = await file.read()
    if len(data) > max_bytes:
        raise HTTPException(status_code=413,
                            detail=f"File too large (max {s_settings.max_upload_mb:.0f} MB)")
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME:
        raise HTTPException(status_code=415, detail="Only PDF, PNG, or JPG files are allowed")

    safe_name = (file.filename or "evidence.bin").replace("/", "_")[:120]
    import hashlib
    digest = hashlib.sha256(data).hexdigest()[:16]
    from pathlib import Path
    folder = Path(s_settings.storage_dir) / str(s.id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{entity_type}-{entity_id}-{digest}{Path(safe_name).suffix or '.bin'}"
    path.write_bytes(data)

    ef = EvidenceFile(
        student_id=s.id, entity_type=entity_type, entity_id=entity_id,
        storage_path=str(path), display_name=file.filename or "evidence",
        mime_type=mime, size_bytes=len(data))
    db.add(ef)
    db.commit()
    return {"status": "ok", "id": ef.id, "stored": ef.storage_path}


@router.get("/evidence/files")
def list_evidence_files(s: Student = Depends(_student), db: Session = Depends(get_db)):
    from app.models import EvidenceFile
    rows = db.execute(
        select(EvidenceFile)
        .where(EvidenceFile.student_id == s.id)
        .order_by(EvidenceFile.uploaded_at.desc())).scalars().all()
    return {"status": "ok", "files": [
        {"id": f.id, "entity_type": f.entity_type, "entity_id": f.entity_id,
         "display_name": f.display_name, "mime_type": f.mime_type,
         "size_bytes": f.size_bytes, "uploaded_at": f.uploaded_at.isoformat()}
        for f in rows]}


# ---------------------------------------------------------------- career
@router.get("/career")
def career(s: Student = Depends(_student), db: Session = Depends(get_db)):
    matches = career_service.latest_matches(db, s)
    best = matches[0] if matches else None
    code = s.target_career_code or (best["career_code"] if best else None)
    detail = career_service.career_detail(db, s, code) if code else None
    return {
        "status": "ok",
        "tracks": [{"code": m["career_code"], "name": m["name"], "description": m["description"]}
                   for m in matches],
        "matches": matches,
        "target_code": s.target_career_code,
        "detail": detail,
    }


@router.post("/career/target")
def set_target(body: TargetCareerIn, s: Student = Depends(_student), db: Session = Depends(get_db)):
    try:
        career_service.set_target_career(db, s, body.career_code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok", "target_career_code": s.target_career_code}


# ---------------------------------------------------------------- optimizer
@router.get("/optimizer")
def optimizer(target_type: str = "GENERAL_READINESS", career_code: str | None = None,
              s: Student = Depends(_student), db: Session = Depends(get_db)):
    result = optimizer_service.optimize(db, s, target_type=target_type, career_code=career_code)
    result["disclaimer"] = ("These projections are model-estimated based on your verified profile and "
                            "assumed skill improvement. They are not guaranteed outcomes.")
    return result


@router.post("/what-if/simulate")
def what_if(body: SimulateIn, s: Student = Depends(_student), db: Session = Depends(get_db)):
    try:
        result = optimizer_service.simulate(db, s, [c.model_dump() for c in body.changes])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result["disclaimer"] = "Hypothetical what-if simulation. This never changes your profile or prediction."
    return result


# ---------------------------------------------------------------- roadmap
@router.post("/roadmap/generate")
def gen_roadmap(body: RoadmapIn, s: Student = Depends(_student), db: Session = Depends(get_db)):
    return roadmap_service.generate(db, s, target_type=body.target_type, career_code=body.career_code)


@router.get("/roadmap")
def get_roadmap(s: Student = Depends(_student), db: Session = Depends(get_db)):
    rm = roadmap_service.latest_roadmap(db, s)
    if not rm:
        return {"status": "empty", "roadmap": None}
    return {"status": "ok", "roadmap": rm}


@router.patch("/roadmap/items/{item_id}")
def update_item(item_id: int, body: RoadmapItemStatusIn,
                s: Student = Depends(_student), db: Session = Depends(get_db)):
    ok = roadmap_service.update_item_status(db, s, item_id, body.status)
    if not ok:
        raise HTTPException(status_code=404, detail="Roadmap item not found")
    return {"status": "ok"}


# ---------------------------------------------------------------- reference
@router.get("/skills")
def list_skills(db: Session = Depends(get_db), s: Student = Depends(_student)):
    rows = db.execute(select(Skill).where(Skill.active == True)  # noqa: E712
                      .order_by(Skill.code)).scalars().all()
    return {"status": "ok", "skills": [
        {"code": x.code, "name": x.name, "category": x.category,
         "benchmark": x.general_benchmark} for x in rows]}


@router.get("/interventions")
def list_interventions(s: Student = Depends(_student), db: Session = Depends(get_db)):
    from app.models import Intervention
    rows = db.execute(select(Intervention)
                      .where(Intervention.active == True)).scalars().all()  # noqa: E712
    return {"status": "ok", "interventions": [
        {"code": i.code, "name": i.name, "skills": i.skill_codes,
         "estimated_weeks": i.estimated_weeks, "description": i.description}
        for i in rows]}
