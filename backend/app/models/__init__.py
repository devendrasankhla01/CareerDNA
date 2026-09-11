"""SQLAlchemy ORM models — the persistent source of truth.

Entity responsibilities (kept deliberately separate):
  users / sessions          — access identity
  students / academic       — institutional academic identity
  skills + student_skills   — competency catalog and per-student state
  projects / internships /  — student-owned employability evidence
  certifications / activities / open_source
  evidence_files            — file metadata (bytes live in storage/)
  verification_*            — human-in-the-loop trust workflow + audit
  predictions               — ML outputs with feature snapshots + XAI cache
  career / roadmap          — derived career intelligence
  import_jobs               — institutional CSV ingestion audit
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.security import utcnow
from app.db.session import Base


def _ts() -> datetime:
    return utcnow()


# ---------------------------------------------------------------- users
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(20), index=True)  # STUDENT|FACULTY|VERIFIER|DEPARTMENT|COMPANY|TPO_ADMIN
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active_session_token: Mapped[str | None] = mapped_column(String(80), index=True)
    # role scoping (set when the TPO provisions the account)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    department: Mapped["Department | None"] = relationship(
        lazy="joined", foreign_keys=[department_id])
    company: Mapped["Company | None"] = relationship(
        lazy="joined", foreign_keys=[company_id])


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuthChallenge(Base):
    """OTP challenge for USN-based student login (hashed, expiring, limited)."""

    __tablename__ = "auth_challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    challenge_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    otp_hash: Mapped[str] = mapped_column(String(80))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)


class FacultyCategory(Base):
    __tablename__ = "faculty_categories"
    __table_args__ = (UniqueConstraint("user_id", "category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(30))  # verification category


# ---------------------------------------------------------------- students
class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True)
    usn: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), unique=True)
    branch: Mapped[str] = mapped_column(String(10), index=True)
    semester: Mapped[int] = mapped_column(Integer, index=True)
    # explicit "I have none yet" declarations (completeness, not missingness)
    no_projects_declared: Mapped[bool] = mapped_column(Boolean, default=False)
    no_internships_declared: Mapped[bool] = mapped_column(Boolean, default=False)
    no_certifications_declared: Mapped[bool] = mapped_column(Boolean, default=False)
    no_activities_declared: Mapped[bool] = mapped_column(Boolean, default=False)
    target_career_code: Mapped[str | None] = mapped_column(String(30))
    available_for_placement: Mapped[bool] = mapped_column(Boolean, default=True)
    profile_version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    user: Mapped[User | None] = relationship(lazy="joined")
    academic: Mapped["AcademicRecord | None"] = relationship(back_populates="student", uselist=False)
    skills: Mapped[list["StudentSkill"]] = relationship(back_populates="student")
    projects: Mapped[list["Project"]] = relationship(back_populates="student")
    internships: Mapped[list["Internship"]] = relationship(back_populates="student")
    certifications: Mapped[list["Certification"]] = relationship(back_populates="student")
    activities: Mapped[list["Activity"]] = relationship(back_populates="student")
    open_sources: Mapped[list["OpenSource"]] = relationship(back_populates="student")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="student")


class AcademicRecord(Base):
    """Institution-owned academic data. Students can never edit these rows.

    tenth/twelfth are optional: institutions may not report them (the model
    imputes missing features during inference).
    """

    __tablename__ = "academic_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), unique=True, index=True)
    cgpa: Mapped[float] = mapped_column(Float)
    tenth_percentage: Mapped[float | None] = mapped_column(Float)
    twelfth_percentage: Mapped[float | None] = mapped_column(Float)
    backlog_history_count: Mapped[int] = mapped_column(Integer, default=0)
    source_import_id: Mapped[int | None] = mapped_column(ForeignKey("import_jobs.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    student: Mapped[Student] = relationship(back_populates="academic")


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20))  # VALIDATED|IMPORTED|FAILED
    rows_detected: Mapped[int] = mapped_column(Integer, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0)
    update_rows: Mapped[int] = mapped_column(Integer, default=0)
    rejected_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors_json: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------- skills
class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(30))  # PROGRAMMING|WEB|DATA|CS_CORE|TOOLS|ASSESSMENT|EXPERIENCE
    general_benchmark: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class StudentSkill(Base):
    """One row per (student, skill) — current state of a competency signal.

    source: SELF_REPORTED | ASSESSMENT | FACULTY | INSTITUTION
    status: PENDING | VERIFIED | CORRECTION_REQUIRED | REJECTED
    A score from ASSESSMENT/INSTITUTION source is trusted immediately;
    SELF_REPORTED claims only become trusted after faculty verification.
    """

    __tablename__ = "student_skills"
    __table_args__ = (UniqueConstraint("student_id", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id"), index=True)
    claimed_level: Mapped[str | None] = mapped_column(String(20))  # Beginner|Intermediate|Advanced
    score: Mapped[float | None] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(25), default="PENDING", index=True)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    student: Mapped[Student] = relationship(back_populates="skills")
    skill: Mapped[Skill] = relationship(lazy="joined")


# ---------------------------------------------------------------- evidence entities
_EVIDENCE_STATUS_DEFAULT = "PENDING"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    tech_stack: Mapped[list | None] = mapped_column(JSON)
    project_type: Mapped[str | None] = mapped_column(String(40))
    team_type: Mapped[str | None] = mapped_column(String(20))
    student_role: Mapped[str | None] = mapped_column(String(120))
    claimed_complexity: Mapped[str | None] = mapped_column(String(20))
    verified_complexity: Mapped[str | None] = mapped_column(String(20))
    github_url: Mapped[str | None] = mapped_column(String(300))
    demo_url: Mapped[str | None] = mapped_column(String(300))
    completion_date: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(25), default=_EVIDENCE_STATUS_DEFAULT, index=True)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    student: Mapped[Student] = relationship(back_populates="projects")


class Internship(Base):
    __tablename__ = "internships"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    organization: Mapped[str] = mapped_column(String(160))
    role: Mapped[str | None] = mapped_column(String(120))
    domain: Mapped[str | None] = mapped_column(String(80))
    start_date: Mapped[str | None] = mapped_column(String(20))
    end_date: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(25), default=_EVIDENCE_STATUS_DEFAULT, index=True)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    student: Mapped[Student] = relationship(back_populates="internships")


class Certification(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    issuer: Mapped[str | None] = mapped_column(String(160))
    credential_id: Mapped[str | None] = mapped_column(String(80))
    credential_url: Mapped[str | None] = mapped_column(String(300))
    issue_date: Mapped[str | None] = mapped_column(String(20))
    expiry_date: Mapped[str | None] = mapped_column(String(20))
    skill_category: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(25), default=_EVIDENCE_STATUS_DEFAULT, index=True)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    student: Mapped[Student] = relationship(back_populates="certifications")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    event_name: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(40))
    organizer: Mapped[str | None] = mapped_column(String(160))
    event_date: Mapped[str | None] = mapped_column(String(20))
    role: Mapped[str | None] = mapped_column(String(60))
    achievement: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(25), default=_EVIDENCE_STATUS_DEFAULT, index=True)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    student: Mapped[Student] = relationship(back_populates="activities")


class OpenSource(Base):
    __tablename__ = "open_source"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    repository_url: Mapped[str] = mapped_column(String(300))
    contribution_type: Mapped[str | None] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(25), default=_EVIDENCE_STATUS_DEFAULT, index=True)
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    student: Mapped[Student] = relationship(back_populates="open_sources")


class EvidenceFile(Base):
    __tablename__ = "evidence_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))  # skill|project|internship|certification|activity|open_source
    entity_id: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(300))
    display_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)


# ---------------------------------------------------------------- verification
class VerificationRequest(Base):
    """One request per student-owned item awaiting human trust decisions.

    Status machine:
      PENDING -> VERIFIED | CORRECTION_REQUIRED | REJECTED
      CORRECTION_REQUIRED -> PENDING (after student resubmission)
    Editing a VERIFIED item returns it to PENDING (new review round).
    """

    __tablename__ = "verification_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    category: Mapped[str] = mapped_column(String(30), index=True)
    status: Mapped[str] = mapped_column(String(25), default="PENDING", index=True)
    resubmission: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    reviews: Mapped[list["VerificationReview"]] = relationship(back_populates="request", order_by="VerificationReview.reviewed_at")


class VerificationReview(Base):
    __tablename__ = "verification_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("verification_requests.id"), index=True)
    verifier_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    previous_status: Mapped[str] = mapped_column(String(25))
    new_status: Mapped[str] = mapped_column(String(25))
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)

    request: Mapped[VerificationRequest] = relationship(back_populates="reviews")


class AcademicIssue(Base):
    """Student-reported academic data discrepancy (admin workflow)."""

    __tablename__ = "academic_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    field: Mapped[str] = mapped_column(String(40))
    current_value: Mapped[str | None] = mapped_column(String(60))
    claimed_value: Mapped[str | None] = mapped_column(String(60))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)


# ---------------------------------------------------------------- analysis
class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(60))
    feature_schema: Mapped[str] = mapped_column(String(40))
    probability: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(20), index=True)
    profile_trust: Mapped[float] = mapped_column(Float)
    data_completeness: Mapped[float] = mapped_column(Float)
    feature_snapshot: Mapped[dict | None] = mapped_column(JSON)
    xai_json: Mapped[dict | None] = mapped_column(JSON)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, index=True)

    student: Mapped[Student] = relationship(back_populates="predictions")


class CareerMatch(Base):
    __tablename__ = "career_matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    career_code: Mapped[str] = mapped_column(String(30), index=True)
    match_score: Mapped[float] = mapped_column(Float)
    major_gap_count: Mapped[int] = mapped_column(Integer, default=0)
    data_coverage: Mapped[float] = mapped_column(Float)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)


class Roadmap(Base):
    __tablename__ = "roadmaps"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    target_type: Mapped[str] = mapped_column(String(30))  # GENERAL_READINESS | CAREER_TRACK
    target_value: Mapped[str | None] = mapped_column(String(40))
    current_readiness: Mapped[float] = mapped_column(Float)
    target_readiness: Mapped[float] = mapped_column(Float)
    estimated_duration: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="CURRENT")  # CURRENT|OUTDATED
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class RoadmapItem(Base):
    __tablename__ = "roadmap_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    roadmap_id: Mapped[int] = mapped_column(ForeignKey("roadmaps.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)
    feature_target: Mapped[str | None] = mapped_column(String(40))
    starting_value: Mapped[str | None] = mapped_column(String(40))
    target_value: Mapped[str | None] = mapped_column(String(40))
    estimated_weeks: Mapped[int | None] = mapped_column(Integer)
    priority: Mapped[str] = mapped_column(String(10))  # Critical|High|Medium
    status: Mapped[str] = mapped_column(String(20), default="NOT_STARTED")  # NOT_STARTED|IN_PROGRESS|COMPLETED
    tasks_json: Mapped[list | None] = mapped_column(JSON)
    milestone: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------- placement
class Department(Base):
    """Institutional department (branch). Department accounts are scoped to one."""

    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)


class Company(Base):
    """Placement company onboarded/approved by the TPO. No public self-registration."""

    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    industry: Mapped[str | None] = mapped_column(String(80))
    website: Mapped[str | None] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE|INACTIVE
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)


class PlacementDrive(Base):
    """A company's placement drive with structured eligibility criteria.

    criteria_version increments whenever eligibility-relevant fields change so
    cached matches can be invalidated.
    """

    __tablename__ = "placement_drives"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(80))
    job_description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(120))
    ctc: Mapped[str | None] = mapped_column(String(40))  # only if TPO/company entered it
    employment_type: Mapped[str | None] = mapped_column(String(40))
    drive_date: Mapped[str | None] = mapped_column(String(20))
    deadline: Mapped[str | None] = mapped_column(String(20))
    open_positions: Mapped[int | None] = mapped_column(Integer)

    # --- mandatory eligibility criteria (None = not required) ---
    min_cgpa: Mapped[float | None] = mapped_column(Float)
    min_tenth: Mapped[float | None] = mapped_column(Float)
    min_twelfth: Mapped[float | None] = mapped_column(Float)
    max_backlogs: Mapped[int | None] = mapped_column(Integer)
    min_readiness: Mapped[float | None] = mapped_column(Float)
    min_coding: Mapped[float | None] = mapped_column(Float)
    min_aptitude: Mapped[float | None] = mapped_column(Float)
    min_communication: Mapped[float | None] = mapped_column(Float)
    project_required: Mapped[bool] = mapped_column(Boolean, default=False)
    internship_required: Mapped[bool] = mapped_column(Boolean, default=False)
    target_branches: Mapped[list | None] = mapped_column(JSON)  # dept codes; empty = all
    eligible_semesters: Mapped[list | None] = mapped_column(JSON)  # e.g. [6, 8]; empty = all

    # --- match-quality inputs ---
    required_skills: Mapped[list | None] = mapped_column(JSON)  # skill codes
    preferred_skills: Mapped[list | None] = mapped_column(JSON)  # skill codes
    preferred_career_code: Mapped[str | None] = mapped_column(String(30))

    status: Mapped[str] = mapped_column(String(20), default="DRAFT", index=True)  # DRAFT|OPEN|CLOSED|COMPLETED
    criteria_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    company: Mapped["Company"] = relationship(lazy="joined")
    candidates: Mapped[list["PlacementCandidate"]] = relationship(back_populates="drive")


# Candidate pipeline statuses (per student per drive)
CANDIDATE_STATUSES = [
    "INTERESTED",        # student expressed interest (institution policy)
    "NOMINATED",         # TPO nominated (human institutional decision)
    "COMPANY_REVIEWING", # company is reviewing
    "SHORTLISTED",       # recruiter shortlist (human recruitment decision)
    "INTERVIEW",         # interview scheduled/in progress
    "SELECTED",          # company selected (recruiter action, not ML)
    "PLACED",            # TPO confirmed official placement
    "NOT_SELECTED",
    "WITHDRAWN",
]


class PlacementCandidate(Base):
    """One student's record in one placement drive (the pipeline row)."""

    __tablename__ = "placement_candidates"
    __table_args__ = (UniqueConstraint("drive_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    drive_id: Mapped[int] = mapped_column(ForeignKey("placement_drives.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="INTERESTED", index=True)

    # last system-computed match (recalculated lazily; auditable, never recruiter-edited)
    match_score: Mapped[float | None] = mapped_column(Float)
    eligible: Mapped[bool | None] = mapped_column(Boolean)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile_version: Mapped[int | None] = mapped_column(Integer)
    criteria_version: Mapped[int | None] = mapped_column(Integer)

    # human decisions (stored separately from AI output, per spec)
    nominated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    nominated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    shortlisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selected_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selection_note: Mapped[str | None] = mapped_column(Text)
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # TPO
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts, onupdate=_ts)

    drive: Mapped["PlacementDrive"] = relationship(back_populates="candidates")
    student: Mapped["Student"] = relationship(lazy="joined")
    history: Mapped[list["PlacementStatusHistory"]] = relationship(back_populates="candidate")


class PlacementStatusHistory(Base):
    """Audit trail of every pipeline status transition."""

    __tablename__ = "placement_status_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("placement_candidates.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    drive_id: Mapped[int] = mapped_column(ForeignKey("placement_drives.id"), index=True)
    old_status: Mapped[str | None] = mapped_column(String(20))
    new_status: Mapped[str] = mapped_column(String(20))
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)

    candidate: Mapped["PlacementCandidate"] = relationship(back_populates="history")


class VerificationAssignment(Base):
    """TPO routes a verification request to a specific verifier (faculty).

    Verifiers only see requests assigned to them; TPO retains full oversight.
    """

    __tablename__ = "verification_assignments"
    __table_args__ = (UniqueConstraint("request_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("verification_requests.id"), index=True)
    verifier_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ts)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")  # PENDING|COMPLETED|REVOKED


Index("ix_placement_candidates_student", "placement_candidates.student_id", "placement_candidates.status")
Index("ix_placement_drives_company", "placement_drives.company_id", "placement_drives.status")


# ---------------------------------------------------------------- reference data
class CareerTrack(Base):
    __tablename__ = "career_tracks"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CareerBenchmark(Base):
    __tablename__ = "career_benchmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    career_code: Mapped[str] = mapped_column(String(30), index=True)
    skill_code: Mapped[str] = mapped_column(String(40))  # may be a pseudo-skill (PROJECT_EXP)
    target_score: Mapped[float] = mapped_column(Float)
    importance_weight: Mapped[float] = mapped_column(Float)
    mandatory: Mapped[bool] = mapped_column(Boolean, default=False)


class Intervention(Base):
    __tablename__ = "interventions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    skill_codes: Mapped[list] = mapped_column(JSON)  # skill/feature codes it targets
    feature_deltas: Mapped[dict] = mapped_column(JSON)  # {"sql_score": 1.0, "project_count": 0.06}
    estimated_weeks: Mapped[int] = mapped_column(Integer)
    career_relevance: Mapped[float] = mapped_column(Float, default=0.5)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


Index("ix_predictions_current", "predictions.student_id", "predictions.is_current")
