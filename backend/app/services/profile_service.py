"""Trusted profile engine.

Responsibilities (single source of truth for profile-derived state):
  * build_feature_vector  — trusted profile -> ML features
  * calculate_trust       — verification-coverage ("Profile Trust") metric
  * calculate_completeness — required-field coverage
  * check_eligibility     — minimum data gate before high-confidence analysis

Policy: the primary (verified) prediction uses only trusted signals:
INSTITUTION / ASSESSMENT sourced rows, FACULTY-verified rows, and derived
values from verified evidence. SELF_REPORTED claims that are still PENDING
are excluded from features (they may be shown in the UI as claimed values).
"""
from __future__ import annotations

from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    Activity,
    AcademicRecord,
    Certification,
    Internship,
    OpenSource,
    Project,
    Skill,
    Student,
    StudentSkill,
)

COMPLEXITY_MAP = {"Basic": 40, "Intermediate": 70, "Advanced": 90}

_PROGRAMMING_SKILLS = ("PYTHON", "JAVA", "JAVASCRIPT", "C_CPP")
_WEB_SKILLS = ("JAVASCRIPT", "HTML_CSS", "REACT", "NODE_JS", "BACKEND", "REST_API")


def _trusted_score(row: StudentSkill | None) -> float | None:
    """A skill value is trusted when verified (assessment/institution rows are
    verified at creation; self claims only after faculty approval)."""
    if row is None:
        return None
    if row.status != "VERIFIED":
        return None
    return row.score


def _skill_map(db: Session, student_id: int) -> dict[str, StudentSkill]:
    rows = db.execute(
        select(StudentSkill, Skill)
        .where(StudentSkill.student_id == student_id)
        .join(Skill, StudentSkill.skill_id == Skill.id)
    ).all()
    return {skill.code: row for row, skill in rows}


def build_feature_vector(db: Session, student: Student) -> dict[str, float | None]:
    skills = _skill_map(db, student.id)
    s = lambda code: _trusted_score(skills.get(code))  # noqa: E731

    def mean_of(codes: tuple[str, ...]) -> float | None:
        vals = [s(c) for c in codes if s(c) is not None]
        return round(mean(vals), 1) if vals else None

    academic = student.academic
    projects = student.projects
    verified_projects = [p for p in projects if p.status == "VERIFIED"]
    internships = student.internships
    verified_internships = [i for i in internships if i.status == "VERIFIED"]
    certifications = student.certifications
    verified_certs = [c for c in certifications if c.status == "VERIFIED"]
    activities = student.activities
    verified_activities = [a for a in activities if a.status == "VERIFIED"]
    oss = [o for o in student.open_sources if o.status == "VERIFIED"]

    f: dict[str, float | None] = {
        "cgpa": academic.cgpa if academic else None,
        "tenth_percentage": academic.tenth_percentage if academic else None,
        "twelfth_percentage": academic.twelfth_percentage if academic else None,
        "backlog_history_count": float(academic.backlog_history_count) if academic else None,
        "programming_score": mean_of(_PROGRAMMING_SKILLS),
        "sql_score": s("SQL"),
        "dsa_score": s("DSA"),
        "web_dev_score": mean_of(_WEB_SKILLS),
        "git_score": s("GIT"),
        "cloud_score": s("CLOUD"),
        "aptitude_score": s("APTITUDE"),
        "logical_score": s("LOGICAL"),
        "coding_score": s("CODING"),
        "communication_score": s("COMMUNICATION"),
        "interview_score": s("INTERVIEW"),
        "presentation_score": s("PRESENTATION"),
        "verified_project_count": float(len(verified_projects)),
        "project_complexity_score": float(
            max((COMPLEXITY_MAP.get(p.verified_complexity or p.claimed_complexity or "", 40)
                 for p in verified_projects), default=0)
        ),
        "verified_internship_count": float(len(verified_internships)),
        "verified_certification_count": float(len(verified_certs)),
        "open_source_score": 50.0 if oss else 0.0,
        "hackathon_score": _activity_score(verified_activities, ("Hackathon", "Technical Competition")),
        "leadership_score": _activity_score(verified_activities, ("Leadership", "Tech Society", "Technical Event")),
    }
    return f


def _activity_score(activities: list[Activity], types: tuple[str, ...]) -> float:
    rel = [a for a in activities if a.event_type in types]
    if not rel:
        return 0.0
    base = min(40.0 + 15.0 * (len(rel) - 1), 70.0)
    bonus = 10.0 if any(a.achievement in ("Winner", "Finalist") or a.role in ("Team Lead", "Organizer") for a in rel) else 0.0
    return round(min(base + bonus, 85.0), 1)


# ---------------------------------------------------------------- trust
def _category_trust(db: Session, student: Student, skills: dict[str, StudentSkill]) -> dict[str, float]:
    w = get_settings().trust_weights

    def frac(present: int, total: int) -> float:
        return 0.0 if total == 0 else present / total

    academic = 1.0 if student.academic else 0.0

    tech_codes = ("PYTHON", "JAVASCRIPT", "SQL", "DSA", "CODING", "BACKEND")
    tech_present = sum(1 for c in tech_codes if _trusted_score(skills.get(c)) is not None)
    technical = frac(tech_present, len(tech_codes))

    projects = student.projects
    verified_p = sum(1 for p in projects if p.status == "VERIFIED")
    projs = frac(verified_p, len(projects)) if projects else 0.0
    interns = student.internships
    verified_i = sum(1 for i in interns if i.status == "VERIFIED")
    ints = frac(verified_i, len(interns)) if interns else 0.0
    practical = 0.5 * projs + 0.5 * ints
    if not projects and not interns:
        practical = 0.0  # no practical evidence at all

    assess_codes = ("CODING", "APTITUDE", "LOGICAL")
    ass_present = sum(1 for c in assess_codes if _trusted_score(skills.get(c)) is not None)
    assessment = frac(ass_present, len(assess_codes))

    comm_codes = ("COMMUNICATION", "INTERVIEW", "PRESENTATION")
    comm_present = sum(1 for c in comm_codes if _trusted_score(skills.get(c)) is not None)
    communication = frac(comm_present, len(comm_codes))

    acts = student.activities
    verified_a = sum(1 for a in acts if a.status == "VERIFIED")
    activity = frac(verified_a, len(acts)) if acts else 0.0

    return {
        "ACADEMIC": academic, "TECHNICAL": technical, "PRACTICAL": practical,
        "ASSESSMENT": assessment, "COMMUNICATION": communication, "ACTIVITY": activity,
    }


def calculate_trust(db: Session, student: Student) -> dict:
    skills = _skill_map(db, student.id)
    cats = _category_trust(db, student, skills)
    w = get_settings().trust_weights
    total_weight = sum(w.values())
    score = sum(w[k] * v for k, v in cats.items()) / total_weight * 100
    score = round(score, 0)
    return {
        "score": score,
        "band": ("Very High" if score >= 90 else "High" if score >= 75
                 else "Moderate" if score >= 60 else "Low"),
        "categories": {k: {"weight": w[k], "value": round(v * 100, 0)} for k, v in cats.items()},
    }


# ---------------------------------------------------------------- completeness
def calculate_completeness(db: Session, student: Student, features: dict[str, float | None]) -> dict:
    """Presence-based (orthogonal to trust): do we have the data at all?"""
    skills = _skill_map(db, student.id)

    def has(code: str) -> bool:
        row = skills.get(code)
        return row is not None  # present (any status) counts for completeness

    checks: list[bool] = []
    details: list[dict] = []

    academic_ok = student.academic is not None
    details.append({"category": "Academic Record", "done": academic_ok})

    tech_present = sum(1 for c in ("PYTHON", "SQL", "DSA", "CODING") if has(c))
    tech_ok = tech_present >= 2
    details.append({"category": "Technical Competency", "done": tech_ok,
                    "note": f"{tech_present} of 4 core signals present"})

    projects_done = len(student.projects) > 0 or student.no_projects_declared
    interns_done = len(student.internships) > 0 or student.no_internships_declared
    pract_ok = projects_done and interns_done
    details.append({"category": "Practical Experience", "done": pract_ok})

    ass_present = sum(1 for c in ("CODING", "APTITUDE") if has(c))
    ass_ok = ass_present >= 1
    details.append({"category": "Assessments", "done": ass_ok})

    comm_ok = has("COMMUNICATION")
    details.append({"category": "Communication", "done": comm_ok})

    done = sum(1 for d in details if d["done"])
    score = round(done / len(details) * 100, 0)
    return {"score": score, "categories": details}


# ---------------------------------------------------------------- eligibility
def check_eligibility(db: Session, student: Student, features: dict[str, float | None]) -> dict:
    """Minimum trusted data required before a readiness analysis.

    Only the institutional academic record is strictly required: the
    readiness pipeline imputes missing assessments (SimpleImputer), so
    institution-imported rosters receive a model-estimated score
    immediately. Assessments and practical experience are tracked as
    *recommended* — they raise trust/completeness and sharpen the signal,
    but they never block the score (which the UI labels as
    model-estimated with a data-completeness indicator).
    """
    requirements = [
        ("Institutional academic record", student.academic is not None),
    ]
    recommended = [
        ("Coding assessment", features.get("coding_score") is not None),
        ("Aptitude assessment", features.get("aptitude_score") is not None),
        ("Communication assessment", features.get("communication_score") is not None),
        ("Practical experience declared",
         len(student.projects) > 0 or len(student.internships) > 0
         or student.no_projects_declared and student.no_internships_declared),
    ]
    missing = [label for label, ok in requirements if not ok]
    missing_recommended = [label for label, ok in recommended if not ok]
    return {
        "eligible": not missing,
        "missing": missing,
        "missing_recommended": missing_recommended,
        "requirements": [{"label": label, "met": ok} for label, ok in requirements + recommended],
    }


def profile_summary(db: Session, student: Student) -> dict:
    features = build_feature_vector(db, student)
    trust = calculate_trust(db, student)
    completeness = calculate_completeness(db, student, features)
    eligibility = check_eligibility(db, student, features)
    return {
        "features": features,
        "trust": trust,
        "completeness": completeness,
        "eligibility": eligibility,
    }
