from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas import InterventionSimIn
from app.services import import_service, intervention_service, tpo_service
from app.services.model_service import model_service
from app.services.auth_service import require_tpo
from app.models import User

router = APIRouter(prefix="/api/tpo", tags=["tpo"])


# ---------------------------------------------------------------- overview
@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(require_tpo),
             branch: str | None = Query(default=None),
             semester: int | None = Query(default=None, ge=1, le=8)):
    if not model_service.available:
        return {"status": "model_unavailable",
                "message": "The readiness model is not deployed yet. Run scripts/train_model.py."}
    return tpo_service.overview(db, branch=branch, semester=semester)


@router.get("/students")
def students(db: Session = Depends(get_db), user: User = Depends(require_tpo),
             search: str | None = Query(default=None),
             branch: str | None = Query(default=None),
             semester: int | None = Query(default=None, ge=1, le=8),
             category: str | None = Query(default=None),
             min_score: float | None = Query(default=None, ge=0, le=100),
             max_score: float | None = Query(default=None, ge=0, le=100),
             trust_min: float | None = Query(default=None, ge=0, le=100),
             page: int = Query(default=1, ge=1),
             page_size: int = Query(default=20, ge=1, le=100),
             sort: str = Query(default="readiness")):
    return tpo_service.student_list(db, search=search, branch=branch, semester=semester,
                                    category=category, min_score=min_score, max_score=max_score,
                                    trust_min=trust_min, page=page, page_size=page_size, sort=sort)


@router.get("/students/{student_id}")
def student_summary(student_id: int, db: Session = Depends(get_db),
                    user: User = Depends(require_tpo)):
    data = tpo_service.student_summary(db, student_id)
    if not data:
        return {"status": "not_found"}
    return {"status": "ok", **data}


@router.get("/skills/catalog")
def skill_catalog(db: Session = Depends(get_db), user: User = Depends(require_tpo)):
    from app.models import Skill
    rows = db.execute(select(Skill).order_by(Skill.name)).scalars().all()
    return {"status": "ok",
            "skills": [{"code": s.code, "name": s.name, "category": s.category,
                        "general_benchmark": s.general_benchmark} for s in rows]}


@router.get("/skills")
def skills(db: Session = Depends(get_db), user: User = Depends(require_tpo),
           branch: str | None = Query(default=None),
           semester: int | None = Query(default=None, ge=1, le=8)):
    return tpo_service.skill_deficits(db, branch=branch, semester=semester)


@router.get("/skills/{skill}/drilldown")
def skill_drilldown(skill: str, db: Session = Depends(get_db),
                    user: User = Depends(require_tpo),
                    branch: str | None = Query(default=None)):
    return tpo_service.skill_drilldown(db, skill, branch=branch)


@router.get("/cohorts/vulnerable")
def vulnerable(db: Session = Depends(get_db), user: User = Depends(require_tpo),
               branch: str | None = Query(default=None)):
    return {"status": "ok", "cohorts": tpo_service.vulnerable_cohorts(db, branch=branch)}


# ---------------------------------------------------------------- interventions
@router.get("/interventions")
def interventions(db: Session = Depends(get_db), user: User = Depends(require_tpo),
                  branch: str | None = Query(default=None),
                  semester: int | None = Query(default=None, ge=1, le=8)):
    return intervention_service.rank_interventions(db, branch=branch, semester=semester)


@router.post("/interventions/simulate")
def simulate(body: InterventionSimIn, db: Session = Depends(get_db),
             user: User = Depends(require_tpo)):
    return intervention_service.simulate(db, body.intervention_code, body.improvement,
                                         branch=body.branch, semester=body.semester)


@router.get("/interventions/{code}/cohort")
def intervention_cohort(code: str, db: Session = Depends(get_db),
                        user: User = Depends(require_tpo)):
    return {"status": "ok", "students": intervention_service.cohort_students(db, code)}


# ---------------------------------------------------------------- import
@router.post("/import/validate")
async def import_validate(file: UploadFile = File(...), db: Session = Depends(get_db),
                          user: User = Depends(require_tpo)):
    s = get_settings()
    data = await file.read()
    max_bytes = int(s.max_upload_mb * 1024 * 1024)
    if len(data) > max_bytes:
        return {"status": "error", "message": f"File too large (max {s.max_upload_mb:.0f} MB)"}
    if not (file.filename or "").lower().endswith(".csv"):
        return {"status": "error", "message": "Only CSV files are supported"}
    return import_service.validate_csv(db, user, data, file.filename or "upload.csv")


@router.post("/import/confirm/{job_id}")
def import_confirm(job_id: int, db: Session = Depends(get_db),
                   user: User = Depends(require_tpo)):
    return import_service.confirm_import(db, user, job_id)


@router.get("/import/jobs")
def import_jobs(db: Session = Depends(get_db), user: User = Depends(require_tpo)):
    return {"status": "ok", "jobs": import_service.job_list(db, user)}


@router.get("/import/template")
def import_template(user: User = Depends(require_tpo)):
    return import_service.template_csv()
