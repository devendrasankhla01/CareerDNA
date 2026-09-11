"""Pydantic request schemas (responses are built as dicts in services)."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- auth
class USNIn(BaseModel):
    usn: str = Field(min_length=4, max_length=30)


class OTPIn(BaseModel):
    usn: str = Field(min_length=4, max_length=30)
    otp: str = Field(min_length=4, max_length=10)


class StaffLoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)


# ---------------------------------------------------------------- student profile
class SkillClaimIn(BaseModel):
    skill_code: str = Field(min_length=2, max_length=40)
    claimed_level: str | None = Field(default=None, max_length=20)
    id: int | None = None


class ProjectIn(BaseModel):
    id: int | None = None
    title: str = Field(min_length=3, max_length=160)
    description: str | None = None
    tech_stack: list[str] | None = None
    project_type: str | None = None
    team_type: str | None = None
    student_role: str | None = None
    claimed_complexity: str | None = Field(default=None, pattern="^(Basic|Intermediate|Advanced)$")
    github_url: str | None = None
    demo_url: str | None = None
    completion_date: str | None = None


class InternshipIn(BaseModel):
    id: int | None = None
    organization: str = Field(min_length=2, max_length=160)
    role: str | None = None
    domain: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class CertificationIn(BaseModel):
    id: int | None = None
    name: str = Field(min_length=2, max_length=160)
    issuer: str | None = None
    credential_id: str | None = None
    credential_url: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    skill_category: str | None = None


class ActivityIn(BaseModel):
    id: int | None = None
    event_name: str = Field(min_length=2, max_length=160)
    event_type: str = Field(min_length=2, max_length=40)
    organizer: str | None = None
    event_date: str | None = None
    role: str | None = None
    achievement: str | None = None


class OpenSourceIn(BaseModel):
    id: int | None = None
    repository_url: str = Field(min_length=4, max_length=300)
    contribution_type: str | None = None
    description: str | None = None


class TargetCareerIn(BaseModel):
    career_code: str | None = Field(default=None, max_length=30)


class RoadmapIn(BaseModel):
    target_type: str = Field(default="GENERAL_READINESS", pattern="^(GENERAL_READINESS|CAREER_TRACK)$")
    career_code: str | None = None


class RoadmapItemStatusIn(BaseModel):
    status: str = Field(pattern="^(NOT_STARTED|IN_PROGRESS|COMPLETED)$")


# ---------------------------------------------------------------- what-if
class SimChangeIn(BaseModel):
    feature: str = Field(min_length=2, max_length=40)
    value: float = Field(ge=0, le=100)


class SimulateIn(BaseModel):
    changes: list[SimChangeIn] = Field(min_length=1, max_length=10)


# ---------------------------------------------------------------- faculty
class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(VERIFIED|CORRECTION_REQUIRED|REJECTED)$")
    note: str | None = Field(default=None, max_length=1000)
    corrections: dict | None = None


# ---------------------------------------------------------------- TPO
class InterventionSimIn(BaseModel):
    intervention_code: str = Field(min_length=2, max_length=40)
    improvement: float = Field(default=20, ge=5, le=40)
    branch: str | None = None
    semester: int | None = Field(default=None, ge=1, le=8)
