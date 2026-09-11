"""TPO institutional CSV import: two-phase validate -> confirm.

This is the institutional data-ingestion path:
  * academic records are written ONLY from here (students can never edit them);
  * a USN not present in the student master CREATES the student (user account +
    profile), so the institution can bootstrap the whole roster from one CSV;
  * institution-provided skill scores are stored as VERIFIED/INSTITUTION rows,
    i.e. trusted immediately by the readiness engine;
  * every job is audited in ImportJob.
"""
from __future__ import annotations

import io
import re

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import utcnow
from app.models import (
    AcademicRecord,
    Activity,
    ImportJob,
    OpenSource,
    Skill,
    Student,
    StudentSkill,
    User,
)

# ---------------------------------------------------------------- column map
REQUIRED_COLUMNS = ["usn", "semester", "cgpa"]

COLUMN_ALIASES = {
    "full_name": "name", "student_name": "name", "student": "name",
    "email_id": "email", "institutional_email": "email",
    "dept": "branch", "department": "branch", "branch_code": "branch",
    "sem": "semester", "sem_no": "semester",
    "gpa": "cgpa",
    "tenthpercentage": "tenth_percentage", "10th_percentage": "tenth_percentage",
    "tenth": "tenth_percentage", "tenth_percent": "tenth_percentage", "10th": "tenth_percentage",
    "twelfthpercentage": "twelfth_percentage", "12th_percentage": "twelfth_percentage",
    "twelfth": "twelfth_percentage", "twelfth_percent": "twelfth_percentage", "12th": "twelfth_percentage",
    "backloghistory": "backlog_history_count", "backlogs": "backlog_history_count",
    "backlog": "backlog_history_count", "backlog_count": "backlog_history_count",
    "c_cpp": "c_cpp", "ccpp": "c_cpp", "c": "c_cpp",
}

# CSV column -> skill code (institution-provided, trusted immediately)
SKILL_COLUMNS = {
    "python": "PYTHON", "java": "JAVA", "javascript": "JAVASCRIPT",
    "c_cpp": "C_CPP", "sql": "SQL", "dsa": "DSA", "git": "GIT",
    "cloud": "CLOUD", "coding": "CODING", "aptitude": "APTITUDE",
    "logical": "LOGICAL", "communication": "COMMUNICATION",
    "interview": "INTERVIEW", "presentation": "PRESENTATION",
}

# CSV column -> verified Activity event_type (value 1/yes/true creates the row)
ACTIVITY_COLUMNS = {
    "hackathon": "Hackathon",
    "leadership": "Leadership",
}

BOOL_COLUMNS = {"open_source", "hackathon", "leadership"}
RECOGNIZED = set(REQUIRED_COLUMNS) | set(COLUMN_ALIASES) | set(SKILL_COLUMNS) \
    | {"name", "email", "branch", "tenth_percentage", "twelfth_percentage",
       "backlog_history_count"} | BOOL_COLUMNS

TEMPLATE_COLUMNS = [
    "usn", "name", "email", "branch", "semester", "cgpa",
    "tenth_percentage", "twelfth_percentage", "backlog_history_count",
    "python", "java", "javascript", "c_cpp", "sql", "dsa", "git", "cloud",
    "coding", "aptitude", "logical", "communication", "interview", "presentation",
    "open_source", "hackathon", "leadership",
]

USN_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-/]{1,29}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def _num(row: dict, field: str, lo: float, hi: float, required: bool,
         errs: list[str]) -> float | None:
    raw = row.get(field)
    if raw is None or (isinstance(raw, float) and pd.isna(raw)) or _clean(raw) == "":
        if required:
            errs.append(f"{field} missing")
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        errs.append(f"{field} not numeric")
        return None
    if not (lo <= v <= hi):
        errs.append(f"{field} out of range ({lo}-{hi})")
        return None
    return v


def _bool(row: dict, field: str) -> bool:
    raw = _clean(row.get(field)).lower()
    return raw in {"1", "yes", "y", "true", "t"}


def _validate_row(row: dict, seen_usns: set[str]) -> list[str]:
    errs: list[str] = []
    usn = _clean(row.get("usn")).upper()
    if not usn:
        return ["USN missing"]
    if usn in seen_usns:
        errs.append("USN duplicated in file")
    if not USN_RE.match(usn):
        errs.append("USN must be 2-30 letters/digits (no spaces)")

    sem = _num(row, "semester", 1, 8, required=True, errs=errs)
    if sem is not None:
        row["semester"] = int(sem)

    _num(row, "cgpa", 0, 10, required=True, errs=errs)
    _num(row, "tenth_percentage", 0, 100, required=False, errs=errs)
    _num(row, "twelfth_percentage", 0, 100, required=False, errs=errs)
    _num(row, "backlog_history_count", 0, 20, required=False, errs=errs)

    name = _clean(row.get("name"))
    if len(name) > 120:
        errs.append("name too long (max 120 chars)")

    email = _clean(row.get("email"))
    if email and not EMAIL_RE.match(email):
        errs.append(f"email '{email}' is not a valid address")

    branch = _clean(row.get("branch")).upper()
    if len(branch) > 10:
        errs.append("branch too long (max 10 chars)")

    for col in SKILL_COLUMNS:
        _num(row, col, 0, 100, required=False, errs=errs)
    for col in BOOL_COLUMNS:
        raw = _clean(row.get(col))
        if raw and raw.lower() not in {"0", "1", "yes", "no", "y", "n", "true", "false", "t", "f"}:
            errs.append(f"{col} must be 0/1 or yes/no")

    seen_usns.add(usn)
    return errs


def _parse_bools(row: dict) -> dict:
    return {col: _bool(row, col) for col in BOOL_COLUMNS}


def validate_csv(db: Session, user: User, file_bytes: bytes, file_name: str) -> dict:
    if user.role not in ("TPO_ADMIN",):
        raise HTTPException(status_code=403, detail="TPO access required")
    s = get_settings()
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    df.columns = [c.strip().lower() for c in df.columns]
    df.rename(columns={k: v for k, v in COLUMN_ALIASES.items() if k in df.columns}, inplace=True)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400,
                            detail=f"Missing required columns: {', '.join(missing)}")

    ignored = sorted(c for c in df.columns if c not in RECOGNIZED)

    records = df.to_dict(orient="records")
    known_usns = {usn for usn in db.execute(select(Student.usn)).scalars()}
    known_emails = {e.lower() for e in db.execute(select(User.email)).scalars() if e}
    file_usns = {_clean(r.get("usn")).upper() for r in records if _clean(r.get("usn"))}
    usn_to_st = {s.usn: s for s in db.execute(
        select(Student).where(Student.usn.in_(file_usns))).scalars()}
    valid_records: list[dict] = []
    errors: list[dict] = []
    valid = 0
    new_students = 0
    updates = 0
    seen_usns: set[str] = set()
    used_derived_emails: set[str] = set()

    for idx, row in enumerate(records):
        row_idx = idx + 2  # 1-based + header
        row_errs = _validate_row(row, seen_usns)
        usn = _clean(row.get("usn")).upper() or f"row {row_idx}"
        # email conflict checks (only when the base row is otherwise valid)
        email = _clean(row.get("email")).lower()
        st = usn_to_st.get(usn)
        if not row_errs and email:
            same_student = st and st.user and (st.user.email or "").lower() == email
            if email in known_emails and not same_student:
                row_errs.append(f"email '{email}' already belongs to another account")
        if not row_errs and not email:
            derived = f"{usn.lower()}@{s.institution_email_domain}"
            same_student = st and st.user and (st.user.email or "").lower() == derived
            if not same_student and (derived in known_emails or derived in used_derived_emails):
                row_errs.append(f"derived email {derived} already in use")
            else:
                row["email"] = derived
                used_derived_emails.add(derived)
        if row_errs:
            errors.append({"row": row_idx, "usn": usn, "errors": row_errs})
            continue
        valid += 1
        row["usn"] = usn
        row["_skill_booleans"] = _parse_bools(row)
        if usn in known_usns:
            updates += 1
        else:
            new_students += 1
        valid_records.append(row)

    job = ImportJob(
        file_name=file_name, uploaded_by=user.id, status="VALIDATED",
        rows_detected=len(df), valid_rows=valid, update_rows=updates,
        rejected_rows=len(errors),
        errors_json=errors[:200],
    )
    db.add(job)
    db.commit()

    _PENDING_JOBS[job.id] = {
        "rows": valid_records,
        "user_id": user.id,
        "valid_usns": [r["usn"] for r in valid_records],
        "new_students": new_students,
        "ignored_columns": ignored,
    }

    msg = ("Upload validated. Review the report, then confirm to import. "
           f"{new_students} new student(s) will be created; {updates} existing student(s) updated.")
    if errors:
        msg = ("Upload validated with errors — only the valid rows will be imported. " + msg)
    return {
        "status": "ok",
        "job_id": job.id,
        "rows_detected": len(df),
        "valid_rows": valid,
        "new_students": new_students,
        "update_rows": updates,
        "rejected_rows": len(errors),
        "ignored_columns": ignored,
        "errors": errors[:200],
        "message": msg,
    }


def confirm_import(db: Session, user: User, job_id: int) -> dict:
    if user.role != "TPO_ADMIN":
        raise HTTPException(status_code=403, detail="TPO access required")
    job = db.get(ImportJob, job_id)
    if not job or job.status != "VALIDATED":
        raise HTTPException(status_code=404, detail="No pending import job")
    pending = _PENDING_JOBS.get(job_id)
    if not pending:
        raise HTTPException(status_code=409, detail="Validation session expired. Re-upload the CSV.")
    if pending["user_id"] != user.id:
        raise HTTPException(status_code=403, detail="Not your import job")

    s = get_settings()
    skill_ids = {sk.code: sk.id for sk in
                 db.execute(select(Skill).where(Skill.code.in_(list(SKILL_COLUMNS.values())))).scalars()}
    usn_to_st = {x.usn: x for x in db.execute(
        select(Student).where(Student.usn.in_(pending["valid_usns"]))).scalars()}

    students_to_analyze: list[Student] = []
    created = 0
    updated = 0

    for row in pending["rows"]:
        usn = row["usn"]
        st = usn_to_st.get(usn)
        is_new = st is None
        if is_new:
            email = row.get("email")
            name = _clean(row.get("name")) or f"Student {usn}"
            user_row = User(role="STUDENT", email=email, display_name=name)
            db.add(user_row)
            db.flush()
            st = Student(
                usn=usn, user_id=user_row.id,
                branch=_clean(row.get("branch")).upper() or "GEN",
                semester=int(row["semester"]),
                # the institution declares that no practical evidence has been
                # recorded yet; students can self-report projects later in the app
                no_projects_declared=True, no_internships_declared=True,
                no_certifications_declared=True, no_activities_declared=True,
            )
            db.add(st)
            db.flush()
            created += 1
        else:
            # upsert basic profile fields the institution owns
            branch = _clean(row.get("branch")).upper()
            if branch:
                st.branch = branch
            st.semester = int(row["semester"])
            if st.user and _clean(row.get("name")):
                st.user.display_name = _clean(row.get("name"))
            updated += 1

        # academic record (institution-only write path)
        rec = db.execute(select(AcademicRecord).where(
            AcademicRecord.student_id == st.id)).scalars().first()
        data = {
            "cgpa": float(row["cgpa"]),
            "tenth_percentage": float(row["tenth_percentage"])
            if row.get("tenth_percentage") is not None and not (
                isinstance(row.get("tenth_percentage"), float)
                and pd.isna(row.get("tenth_percentage"))) else None,
            "twelfth_percentage": float(row["twelfth_percentage"])
            if row.get("twelfth_percentage") is not None and not (
                isinstance(row.get("twelfth_percentage"), float)
                and pd.isna(row.get("twelfth_percentage"))) else None,
            "backlog_history_count": int(float(row.get("backlog_history_count") or 0)),
            "source_import_id": job.id,
        }
        if rec:
            for k, v in data.items():
                setattr(rec, k, v)
        else:
            rec = AcademicRecord(student_id=st.id, **data)
            db.add(rec)

        # institution-provided skill scores (trusted immediately)
        bools = row.get("_skill_booleans", {})
        for col, code in SKILL_COLUMNS.items():
            raw = row.get(col)
            if raw is None or (isinstance(raw, float) and pd.isna(raw)) or _clean(raw) == "":
                continue
            score = float(raw)
            skill_id = skill_ids.get(code)
            if skill_id is None:
                continue
            ss = next((x for x in st.skills if x.skill_id == skill_id), None)
            if ss:
                ss.score = score
                ss.source = "INSTITUTION"
                ss.status = "VERIFIED"
            else:
                db.add(StudentSkill(student_id=st.id, skill_id=skill_id,
                                    score=score, source="INSTITUTION",
                                    status="VERIFIED"))

        # verified activity rows from booleans
        for col, event_type in ACTIVITY_COLUMNS.items():
            if bools.get(col):
                exists = any(a.event_type == event_type and a.status == "VERIFIED"
                             for a in st.activities)
                if not exists:
                    db.add(Activity(student_id=st.id, event_type=event_type,
                                    event_name=f"{event_type} (institutional record)",
                                    status="VERIFIED"))
        if bools.get("open_source"):
            if not any(o.status == "VERIFIED" for o in st.open_sources):
                db.add(OpenSource(student_id=st.id,
                                  repository_url="https://github.com/institutional-record",
                                  contribution_type="Institutional record",
                                  status="VERIFIED"))

        students_to_analyze.append(st)

    job.status = "IMPORTED"
    job.completed_at = utcnow()
    db.commit()
    _PENDING_JOBS.pop(job_id, None)

    # score every imported student immediately (idempotent; skips ineligible)
    from app.services.analysis_service import run_analysis
    analyzed = 0
    score_errors = 0
    for st in students_to_analyze:
        try:
            if run_analysis(db, st, reason="import") is not None:
                analyzed += 1
        except Exception:
            score_errors += 1

    total = created + updated
    msg = (f"Imported {total} student(s) (upsert by USN): "
           f"{created} created, {updated} updated, {analyzed} scored.")
    if score_errors:
        msg += f" {score_errors} student(s) could not be scored yet."
    return {
        "status": "ok",
        "job_id": job_id,
        "imported_rows": total,
        "new_students": created,
        "updated_students": updated,
        "analyzed": analyzed,
        "score_errors": score_errors,
        "message": msg,
    }


def job_list(db: Session, user: User) -> list[dict]:
    if user.role != "TPO_ADMIN":
        raise HTTPException(status_code=403, detail="TPO access required")
    jobs = db.execute(select(ImportJob).order_by(ImportJob.created_at.desc()).limit(20)).scalars()
    return [
        {"id": j.id, "file_name": j.file_name, "status": j.status,
         "rows_detected": j.rows_detected, "valid_rows": j.valid_rows,
         "update_rows": j.update_rows, "rejected_rows": j.rejected_rows,
         "created_at": j.created_at.isoformat(),
         "completed_at": j.completed_at.isoformat() if j.completed_at else None,
         "errors": (j.errors_json or [])[:50]}
        for j in jobs
    ]


def template_csv() -> bytes:
    df = pd.DataFrame(columns=TEMPLATE_COLUMNS)
    return df.to_csv(index=False).encode()


# in-memory pending validation sessions (single-process demo)
_PENDING_JOBS: dict[int, dict] = {}
