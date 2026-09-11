"""Document storage and Activity Logs API backed by MongoDB."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import mongo
from app.models import Student, User
from app.services.auth_service import get_current_user, require_student, require_tpo

router = APIRouter(prefix="/api/documents", tags=["documents"])


class ResumeIn(BaseModel):
    summary: str | None = None
    skills: list[str] | None = None
    experience: list[dict[str, Any]] | None = None
    education: list[dict[str, Any]] | None = None
    projects: list[dict[str, Any]] | None = None
    certifications: list[dict[str, Any]] | None = None
    custom_sections: dict[str, Any] | None = None


class PortfolioIn(BaseModel):
    item_type: str = "project"  # project | case_study | certification | publication
    title: str
    description: str | None = None
    media_urls: list[str] | None = None
    github_metadata: dict[str, Any] | None = None
    tech_stack: list[str] | None = None
    metrics: dict[str, Any] | None = None


@router.get("/status")
def mongo_health_status():
    """Returns the live MongoDB connection status."""
    return {"status": "ok", "mongodb": mongo.check_mongo_status()}


# ---------------------------------------------------------------- Student Resumes
@router.post("/student/resume")
def save_resume(
    data: ResumeIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_student),
):
    """Save or update student resume in MongoDB."""
    st = db.execute(select(Student).where(Student.user_id == user.id)).scalars().first()
    if not st:
        raise HTTPException(404, "Student profile not found")

    saved = mongo.save_student_resume_document(
        student_id=st.id,
        usn=st.usn,
        resume_data=data.model_dump(),
    )

    mongo.log_activity(
        action="RESUME_UPDATED",
        actor_id=user.id,
        actor_role=user.role,
        target_type="STUDENT_RESUME",
        target_id=st.id,
        details={"usn": st.usn},
    )

    return {"status": "ok", "document": saved}


@router.get("/student/{student_id}/resume")
def get_resume(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve a student's resume document from MongoDB."""
    # Authorization: Student themselves, or staff (TPO, DEPT, FACULTY, COMPANY)
    if user.role == "STUDENT":
        st = db.execute(select(Student).where(Student.user_id == user.id)).scalars().first()
        if not st or st.id != student_id:
            raise HTTPException(403, "Not authorized to view this student's resume")

    doc = mongo.get_student_resume_document(student_id)
    return {"status": "ok", "document": doc}


# ---------------------------------------------------------------- Portfolio Items
@router.post("/student/portfolio")
def add_portfolio_item(
    data: PortfolioIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_student),
):
    """Add rich portfolio/project documentation to MongoDB."""
    st = db.execute(select(Student).where(Student.user_id == user.id)).scalars().first()
    if not st:
        raise HTTPException(404, "Student profile not found")

    item = mongo.save_student_portfolio_item(
        student_id=st.id,
        usn=st.usn,
        item_type=data.item_type,
        item_data=data.model_dump(),
    )

    mongo.log_activity(
        action="PORTFOLIO_ITEM_ADDED",
        actor_id=user.id,
        actor_role=user.role,
        target_type="STUDENT_PORTFOLIO",
        target_id=st.id,
        details={"title": data.title, "item_type": data.item_type},
    )

    return {"status": "ok", "item": item}


@router.get("/student/{student_id}/portfolio")
def get_portfolio_items(
    student_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve portfolio items for a student."""
    items = mongo.get_student_portfolio_items(student_id)
    return {"status": "ok", "student_id": student_id, "items": items}


# ---------------------------------------------------------------- Activity Logs
@router.get("/activity-logs")
def list_activity_logs(
    limit: int = 50,
    actor_role: str | None = None,
    target_type: str | None = None,
    user: User = Depends(get_current_user),
):
    """Fetch live activity logs from MongoDB."""
    if user.role not in ("TPO_ADMIN", "DEPARTMENT", "FACULTY"):
        raise HTTPException(403, "Staff authorization required for activity logs")

    logs = mongo.get_activity_logs(
        limit=min(limit, 200),
        actor_role=actor_role,
        target_type=target_type,
    )
    return {"status": "ok", "logs": logs, "count": len(logs)}
