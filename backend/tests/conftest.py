"""Shared fixtures: isolated temp DB + small deterministic seed + TestClient.

The full 600-student demo seed is used by the live demo; the pytest suite
uses a compact deterministic seed so tests run fast.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

_TMPDIR = tempfile.mkdtemp(prefix="careerdna-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMPDIR}/test.db"
os.environ["DEMO_MODE"] = "true"
os.environ["MODEL_DIR"] = str(BASE / "artifacts")
os.environ["INTERVENTION_MIN_POPULATION"] = "5"  # small test cohort

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    AcademicRecord,
    FacultyCategory,
    Project,
    Skill,
    Student,
    StudentSkill,
    User,
    VerificationRequest,
)
from app.services.model_service import model_service  # noqa: E402
from app.services.reference_service import ensure_reference_data  # noqa: E402
import app.main  # noqa: E402


def _seed_small() -> None:
    db = SessionLocal()
    ensure_reference_data(db)

    def user(role, email, pw, name):
        u = User(role=role, email=email,
                 password_hash=hash_password(pw) if pw else None, display_name=name)
        db.add(u)
        db.flush()
        return u

    def student(usn, name, branch, sem, cgpa, skills: dict, **kw):
        st = Student(usn=usn, branch=branch, semester=sem, **kw)
        db.add(st)
        db.flush()
        u = user("STUDENT", f"{usn.lower()}@northfielddemo.edu", None, name)
        st.user_id = u.id
        db.add(AcademicRecord(student_id=st.id, cgpa=cgpa, tenth_percentage=80.0,
                              twelfth_percentage=78.0, backlog_history_count=0))
        skill_rows = {s.code: s for s in db.execute(select(Skill)).scalars()}
        for code, score in skills.items():
            db.add(StudentSkill(student_id=st.id, skill_id=skill_rows[code].id,
                                score=score, source="ASSESSMENT", status="VERIFIED"))
        return st

    student("1PM24CS101", "Test Alpha", "CSE", 4, 8.2,
            {"CODING": 75, "APTITUDE": 72, "LOGICAL": 70, "COMMUNICATION": 60,
             "INTERVIEW": 58, "PRESENTATION": 55, "SQL": 68, "DSA": 70, "PYTHON": 72,
             "JAVASCRIPT": 65, "GIT": 60, "CLOUD": 45})
    weak = student("1PM24IS102", "Test Beta", "ISE", 4, 6.1,
                   {"CODING": 40, "APTITUDE": 42, "LOGICAL": 45, "COMMUNICATION": 38,
                    "INTERVIEW": 40, "PRESENTATION": 42, "SQL": 30, "DSA": 38, "PYTHON": 45,
                    "JAVASCRIPT": 40, "GIT": 35, "CLOUD": 25})
    db.flush()
    # give Alpha a verified project so the profile is eligible
    alpha = db.execute(select(Student).where(Student.usn == "1PM24CS101")).scalars().first()
    db.add(Project(student_id=alpha.id, title="Alpha Project", claimed_complexity="Intermediate",
                   verified_complexity="Intermediate", tech_stack=["React", "Node.js"],
                   status="VERIFIED"))
    proj = Project(student_id=weak.id, title="Test Project", claimed_complexity="Basic",
                   tech_stack=["Python"], status="PENDING")
    db.add(proj)
    db.flush()
    db.add(VerificationRequest(student_id=weak.id, entity_type="project",
                               entity_id=proj.id, category="PROJECT", status="PENDING"))

    # small deterministic cohort (so heatmaps/interventions have population)
    import random as _rnd
    rng = _rnd.Random(4242)
    base_skills = ["CODING", "APTITUDE", "LOGICAL", "COMMUNICATION", "INTERVIEW",
                   "PRESENTATION", "SQL", "DSA", "PYTHON", "JAVASCRIPT", "GIT", "CLOUD"]
    for i in range(1, 13):
        level = rng.uniform(0.25, 0.95)
        skills = {c: max(15, min(95, int(20 + 65 * level + rng.gauss(0, 8)))) for c in base_skills}
        st = student(f"1PM24CS3{i:02d}", f"Cohort Student {i}", "CSE" if i % 2 else "ISE",
                     rng.choice([4, 6]), round(rng.uniform(5.5, 8.8), 2), skills)
        if rng.random() < 0.7:
            db.add(Project(student_id=st.id, title=f"Cohort Project {i}",
                           claimed_complexity=rng.choice(["Basic", "Intermediate"]),
                           tech_stack=["Python"], status=rng.choice(["VERIFIED", "PENDING"])))
        if rng.random() < 0.5:
            st.no_internships_declared = True

    f1 = user("FACULTY", "f1@test.edu", "Pass1234!", "Faculty One")
    for cat in ("PROJECT", "TECHNICAL_SKILL"):
        db.add(FacultyCategory(user_id=f1.id, category=cat))
    f2 = user("FACULTY", "f2@test.edu", "Pass1234!", "Faculty Two")
    db.add(FacultyCategory(user_id=f2.id, category="INTERNSHIP"))
    user("TPO_ADMIN", "tpo@test.edu", "Pass1234!", "TPO Admin")
    db.commit()

    # run readiness analyses for the test students
    from app.services.analysis_service import run_analysis
    for st in db.execute(select(Student)).scalars():
        run_analysis(db, st, reason="test_seed")
    db.commit()
    db.close()


@pytest.fixture(scope="session")
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    if not model_service.available:
        assert model_service.load(), "model artifact must exist (run scripts.train_model)"
    _seed_small()
    with TestClient(app.main.app) as c:
        yield c


def login(client: TestClient, url: str, **body) -> str:
    r = client.post(url, json=body)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def tokens(client):
    t = {}
    t["student"] = _student_token(client, "1PM24CS101")
    t["weak_student"] = _student_token(client, "1PM24IS102")
    t["faculty_proj"] = login(client, "/api/auth/staff/login",
                              email="f1@test.edu", password="Pass1234!")
    t["faculty_intern"] = login(client, "/api/auth/staff/login",
                                email="f2@test.edu", password="Pass1234!")
    t["tpo"] = login(client, "/api/auth/staff/login",
                     email="tpo@test.edu", password="Pass1234!")
    # New oversight flow: verifiers only act on requests the TPO ASSIGNS to
    # them. Assign all PENDING requests to the PROJECT/TECHNICAL faculty (f1).
    hdr_tpo = {"Authorization": f"Bearer {t['tpo']}"}
    verifiers = client.get("/api/tpo/verifiers", headers=hdr_tpo).json()["verifiers"]
    f1_id = next(v["id"] for v in verifiers if v["email"] == "f1@test.edu")
    center = client.get("/api/tpo/verification-center", headers=hdr_tpo).json()
    pending = [i["request_id"] for i in center["items"] if i["status"] == "PENDING"]
    if pending:
        r = client.post("/api/tpo/verification-center/assign",
                        json={"request_ids": pending, "verifier_id": f1_id}, headers=hdr_tpo)
        assert r.status_code == 200, r.text
    return t


def _student_token(client: TestClient, usn: str) -> str:
    r = client.post("/api/auth/student/request-otp", json={"usn": usn})
    assert r.status_code == 200, r.text
    r = client.post("/api/auth/student/verify-otp", json={"usn": usn, "otp": "246810"})
    assert r.status_code == 200, r.text
    return r.json()["token"]
