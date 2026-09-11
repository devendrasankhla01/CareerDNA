"""Delete ALL student data (profiles, users, analyses, placement records).

Staff, departments, companies and drives are kept.

Usage:
  .venv/bin/python -m scripts.wipe_students            # wipe all students
"""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import User

# children first (FK-safe order) — tables that reference students.student_id
STUDENT_TABLES = [
    "placement_status_history",
    "placement_candidates",
    "verification_requests",
    "predictions",
    "career_matches",
    "roadmaps",
    "academic_records",
    "academic_issues",
    "activities",
    "auth_challenges",
    "certifications",
    "evidence_files",
    "internships",
    "open_source",
    "projects",
    "student_skills",
]


def main() -> None:
    from sqlalchemy import text

    db: Session = SessionLocal()
    student_ids = [r[0] for r in db.execute(text("SELECT id FROM students")).all()]
    if not student_ids:
        print("No students to delete.")
        return
    placeholders = ", ".join(str(i) for i in student_ids)

    # verification tables reference the requests, which reference students
    vr_ids = [r[0] for r in db.execute(
        text(f"SELECT id FROM verification_requests WHERE student_id IN ({placeholders})")).all()]
    if vr_ids:
        vp = ", ".join(str(i) for i in vr_ids)
        db.execute(text(f"DELETE FROM verification_assignments WHERE verification_request_id IN ({vp})"))
        db.execute(text(f"DELETE FROM verification_reviews WHERE verification_request_id IN ({vp})"))

    for t in STUDENT_TABLES:
        n = db.execute(text(f"DELETE FROM {t} WHERE student_id IN ({placeholders})")).rowcount
        print(f"  {t}: {n} row(s) deleted")

    user_ids = [r[0] for r in db.execute(
        text(f"SELECT user_id FROM students WHERE id IN ({placeholders}) AND user_id IS NOT NULL")).all()]
    n = db.execute(text(f"DELETE FROM students WHERE id IN ({placeholders})")).rowcount
    print(f"  students: {n} deleted")
    if user_ids:
        up = ", ".join(str(i) for i in user_ids)
        db.execute(text(f"DELETE FROM sessions WHERE user_id IN ({up})"))
    n = db.execute(
        text(f"DELETE FROM users WHERE id IN ({up}) AND role = 'STUDENT'")).rowcount
    print(f"  users (STUDENT): {n} deleted")

    # import jobs only exist because of student imports — clear for a clean slate
    n = db.execute(text("DELETE FROM import_jobs")).rowcount
    print(f"  import_jobs: {n} deleted")
    db.commit()
    print(f"Wiped {len(student_ids)} student(s). Institution is now empty "
          "(staff/departments/companies kept).")
    db.close()


if __name__ == "__main__":
    main()
