from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import DecisionIn
from app.services import verification_service
from app.services.auth_service import get_current_user, require_staff, require_verifier
from app.models import User

router = APIRouter(prefix="/api/faculty", tags=["faculty"])


@router.get("/queue")
def queue(db: Session = Depends(get_db),
          user: User = Depends(require_verifier),
          category: str | None = Query(default=None),
          status: str = Query(default="PENDING",
                              pattern="^(PENDING|VERIFIED|CORRECTION_REQUIRED|REJECTED)$"),
          page: int = Query(default=1, ge=1),
          page_size: int = Query(default=15, ge=1, le=100)):
    return verification_service.faculty_queue(db, user, category=category,
                                              status=status, page=page, page_size=page_size)


@router.get("/queue/{request_id}")
def detail(request_id: int, db: Session = Depends(get_db),
           user: User = Depends(require_verifier)):
    return verification_service.faculty_detail(db, user, request_id)


@router.post("/queue/{request_id}/decide")
def decide(request_id: int, body: DecisionIn, db: Session = Depends(get_db),
           user: User = Depends(require_verifier)):
    return verification_service.faculty_decide(db, user, request_id,
                                               body.decision, body.note, body.corrections)


@router.get("/me")
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"status": "ok", "user": user.role, "categories": []}
