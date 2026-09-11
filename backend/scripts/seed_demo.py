"""Seed a deterministic synthetic demo institution.

Order (per architecture): reference data -> staff users -> students +
institutional academics -> employability evidence (with verification states)
-> verification requests -> (if model trained) readiness analyses.

Commands:
  .venv/bin/python -m scripts.seed_demo        # seed (idempotent: clears first)
  .venv/bin/python -m scripts.reset_demo       # delete DB + reseed
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.models import *  # noqa: F403, E402
from scripts import generate_data as gd  # noqa: E402

SEED = 20260911
BASE = Path(__file__).resolve().parents[1]
STORAGE = BASE / "storage" / "evidence"

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Sai", "Ishaan", "Aryan", "Kabir", "Rohan", "Dev",
    "Ananya", "Diya", "Ishita", "Sanya", "Prisha", "Aisha", "Navya", "Riya", "Meera", "Tara",
    "Kavya", "Anaya", "Sneha", "Pooja", "Rahul", "Vikram", "Nikhil", "Karan", "Siddharth", "Amit",
    "Priya", "Divya", "Shreya", "Pooja", "Nandini", "Aishwarya", "Varun", "Harsh", "Yash", "Manish",
    "Sneha", "Ritika", "Tanvi", "Shruti", "Lakshmi", "Gauri", "Aditi", "Nidhi",
]
LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Reddy", "Nair", "Iyer", "Menon", "Kulkarni", "Deshmukh", "Raghavan",
    "Chopra", "Gupta", "Mehta", "Joshi", "Kulkarni", "Bhat", "Rao", "Shetty", "Nambiar", "Pillai",
    "Sethi", "Kapoor", "Malhotra", "Singh", "Chauhan", "Bhardwaj", "Taneja", "Arora", "Ghosh", "Banerjee",
    "Bose", "Sarkar", "Chakraborty", "Mukherjee",
]

PROJECT_TITLES = [
    "Campus Events Portal", "Inventory Management Web App", "Student Feedback Dashboard",
    "Library Book Tracking System", "Expense Splitter App", "Quiz Battle Platform",
    "Recipe Finder with Search", "Weather Analytics Dashboard", "Task Management API",
    "Chat App with Rooms", "Movie Recommendations Engine", "Attendance Analytics Tool",
    "E-Commerce Admin Panel", "Health Metrics Tracker", "Auction House Frontend",
]
PROJECT_STACKS = [
    ["React", "Node.js", "PostgreSQL"], ["React", "FastAPI", "PostgreSQL"],
    ["JavaScript", "Express", "MongoDB"], ["Python", "Flask", "SQLite"],
    ["React", "Spring Boot", "MySQL"], ["Vue", "Django", "PostgreSQL"],
]
CERT_POOL = [
    ("AWS Cloud Practitioner", "Amazon Web Services", "CLOUD"),
    ("Google Data Analytics", "Google", "DATA"),
    ("SQL for Data Science", "Udacity", "DATABASE"),
    ("Meta Front-End Developer", "Meta", "WEB"),
    ("TensorFlow Developer Certificate", "Google", "DATA"),
    ("MongoDB Associate", "MongoDB University", "DATABASE"),
    ("Java Programming Fundamentals", "Coursera", "PROGRAMMING"),
    ("Azure Fundamentals", "Microsoft", "CLOUD"),
]
INTERNSHIP_ORGS = [
    ("TechBridge Solutions", "Software Development Intern"),
    ("NovaPay Systems", "Backend Intern"),
    ("CloudNine Labs", "DevOps Trainee"),
    ("DataMint Analytics", "Data Analyst Intern"),
    ("SoftEdge Studios", "Frontend Intern"),
    ("PixelWorks", "QA Intern"),
]
ACTIVITIES_POOL = [
    ("HackNorth 2026", "Hackathon", "Finalist"),
    ("CodeSprint National", "Technical Competition", "Winner"),
    ("Smart India Hackathon", "Hackathon", "Team Lead"),
    ("TechFest 2025", "Technical Event", "Organizer"),
    ("IEEE Student Branch", "Tech Society", "Core Member"),
    ("Tech Quiz Finals", "Technical Competition", "Finalist"),
    ("Departmental Cultural Fest", "Leadership", "Event Lead"),
]
OSS_REPOS = [
    ("https://github.com/opensource-india/fastapi-utils", "Bug fixes and docs"),
    ("https://github.com/pandas-dev/pandas", "Documentation improvements"),
    ("https://github.com/vercel/next.js", "Minor UI bug fix"),
]

SKILL_CATALOG = [
    ("PYTHON", "Python", "PROGRAMMING", 70), ("JAVA", "Java", "PROGRAMMING", 60),
    ("JAVASCRIPT", "JavaScript", "WEB", 70), ("HTML_CSS", "HTML/CSS", "WEB", 65),
    ("REACT", "React", "WEB", 70), ("NODE_JS", "Node.js", "WEB", 60),
    ("BACKEND", "Backend Development", "WEB", 70), ("REST_API", "REST APIs", "WEB", 65),
    ("C_CPP", "C/C++", "PROGRAMMING", 55),
    ("SQL", "SQL", "DATABASE", 70), ("DBMS", "DBMS", "DATABASE", 60),
    ("DSA", "Data Structures & Algorithms", "CS_CORE", 65),
    ("CODING", "Coding Assessment", "ASSESSMENT", 70),
    ("APTITUDE", "Quantitative Aptitude", "ASSESSMENT", 70),
    ("LOGICAL", "Logical Reasoning", "ASSESSMENT", 70),
    ("COMMUNICATION", "Communication", "ASSESSMENT", 65),
    ("INTERVIEW", "Mock Interview", "ASSESSMENT", 65),
    ("PRESENTATION", "Presentation", "ASSESSMENT", 60),
    ("GIT", "Git/GitHub", "TOOLS", 65), ("CLOUD", "Cloud Fundamentals", "TOOLS", 55),
    ("PANDAS", "Pandas", "DATA", 65), ("STATISTICS", "Statistics", "DATA", 70),
    ("EXCEL", "Excel", "DATA", 60), ("POWER_BI", "Power BI", "DATA", 55),
]

CAREER_TRACKS = [
    ("FULL_STACK", "Full-Stack Developer",
     "End-to-end product development: frontend frameworks, backend services, databases, and shipping real projects."),
    ("DATA_ANALYST", "Data Analyst",
     "Turning raw data into decisions: SQL, Python data tooling, statistics, and business intelligence dashboards."),
]

FULL_STACK_BENCH = [
    ("JAVASCRIPT", 75, 0.14, True), ("HTML_CSS", 70, 0.06, False), ("REACT", 70, 0.10, False),
    ("BACKEND", 70, 0.12, True), ("REST_API", 65, 0.06, False), ("SQL", 65, 0.10, True),
    ("GIT", 60, 0.06, False), ("PYTHON", 60, 0.06, False), ("DSA", 55, 0.08, False),
    ("COMMUNICATION", 60, 0.08, False), ("PROJECT_EXP", 70, 0.14, True),
]
DATA_ANALYST_BENCH = [
    ("PYTHON", 70, 0.12, True), ("SQL", 75, 0.14, True), ("STATISTICS", 70, 0.10, True),
    ("PANDAS", 70, 0.10, False), ("EXCEL", 65, 0.06, False), ("POWER_BI", 60, 0.08, False),
    ("DSA", 50, 0.04, False), ("APTITUDE", 70, 0.10, False), ("PROJECT_EXP", 65, 0.12, False),
    ("COMMUNICATION", 60, 0.08, False), ("CLOUD", 40, 0.06, False),
]

INTERVENTIONS = [
    ("SQL_BOOTCAMP", "SQL & Database Bootcamp", ["SQL"], {"sql_score": 1.0}, 2, 1.0,
     "Intensive relational modelling, joins, aggregation, and query optimization."),
    ("DSA_SPRINT", "DSA & Problem-Solving Sprint", ["DSA", "CODING"], {"dsa_score": 1.0, "coding_score": 0.5}, 3, 0.9,
     "Structured problem solving, complexity analysis, and coding assessment practice."),
    ("COMM_WORKSHOP", "Interview Communication Workshop", ["COMMUNICATION", "INTERVIEW"],
     {"communication_score": 1.0, "interview_score": 0.7}, 2, 0.8,
     "STAR storytelling, project explanation, and mock interview drills."),
    ("FULLSTACK_SPRINT", "Full-Stack Project Sprint", ["WEB", "PROJECT"], {"web_dev_score": 0.8, "verified_project_count": 0.5}, 4, 0.7,
     "Ship one role-relevant full-stack application with a database and deployment."),
    ("DATA_SPRINT", "Data Analytics Project Sprint", ["DATA", "SQL"], {"sql_score": 0.7, "coding_score": 0.5}, 4, 0.6,
     "Real-dataset cleaning, SQL analysis, and a BI dashboard build."),
    ("APTITUDE_PROGRAM", "Aptitude Preparation Program", ["APTITUDE", "LOGICAL"],
     {"aptitude_score": 1.0, "logical_score": 0.8}, 3, 0.7,
     "Quantitative and logical reasoning practice with timed assessments."),
    ("GIT_WORKSHOP", "Git/GitHub Practical Workshop", ["GIT"], {"git_score": 1.0}, 1, 0.5,
     "Branching, pull requests, and collaborative workflows on real repositories."),
    ("CLOUD_WORKSHOP", "Cloud Fundamentals Workshop", ["CLOUD"], {"cloud_score": 1.0}, 2, 0.4,
     "Core cloud concepts: compute, storage, networking, and one hands-on deployment."),
]

LEVELS = ["Beginner", "Intermediate", "Advanced"]
LEVEL_MAP = {"Beginner": 40, "Intermediate": 65, "Advanced": 85}


def make_simple_pdf(title: str, lines: list[str]) -> bytes:
    """Minimal single-page PDF (no external libraries)."""
    def esc(s: str) -> str:
        s = (s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)"))
        # PDF latin-1: normalize non-ASCII to plain ASCII
        s = (s.replace("\u2014", "-").replace("\u2013", "-").replace("\u2019", "'")
              .replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
              .replace("\u2026", "..."))
        return s.encode("latin-1", "replace").decode("latin-1")

    content = [f"BT /F1 16 Tf 60 760 Td ({esc(title)}) Tj ET"]
    y = 720
    for ln in lines:
        content.append(f"BT /F1 11 Tf 60 {y} Td ({esc(ln)}) Tj ET")
        y -= 18
    stream = "\n".join(content).encode("latin-1")
    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>")
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    return bytes(out)


def save_evidence(student_id: int, entity_type: str, entity_id: int, name: str, content: bytes,
                  mime: str, db: Session) -> EvidenceFile:
    STUDORAGE = STORAGE / str(student_id)
    STUDORAGE.mkdir(parents=True, exist_ok=True)
    import hashlib
    digest = hashlib.sha256(f"{entity_type}:{entity_id}:{name}".encode()).hexdigest()[:12]
    suffix = name.rsplit(".", 1)[-1]
    path = STUDORAGE / f"{digest}.{suffix}"
    path.write_bytes(content)
    ev = EvidenceFile(student_id=student_id, entity_type=entity_type, entity_id=entity_id,
                      storage_path=str(path.relative_to(BASE)), display_name=name,
                      mime_type=mime, size_bytes=len(content))
    db.add(ev)
    return ev


def clear_all(db: Session) -> None:
    for t in reversed(Base.metadata.sorted_tables):
        db.execute(t.delete())
    db.commit()


def seed_reference(db: Session) -> None:
    for code, name, cat, bench in SKILL_CATALOG:
        db.add(Skill(code=code, name=name, category=cat, general_benchmark=bench))
    for code, name, desc in CAREER_TRACKS:
        db.add(CareerTrack(code=code, name=name, description=desc))
    for code, target, weight, mandatory in FULL_STACK_BENCH:
        db.add(CareerBenchmark(career_code="FULL_STACK", skill_code=code, target_score=target,
                               importance_weight=weight, mandatory=mandatory))
    for code, target, weight, mandatory in DATA_ANALYST_BENCH:
        db.add(CareerBenchmark(career_code="DATA_ANALYST", skill_code=code, target_score=target,
                               importance_weight=weight, mandatory=mandatory))
    for code, name, skills, deltas, weeks, rel, desc in INTERVENTIONS:
        db.add(Intervention(code=code, name=name, skill_codes=skills, feature_deltas=deltas,
                            estimated_weeks=weeks, career_relevance=rel, description=desc))
    db.commit()


def seed_staff(db: Session) -> dict:
    staff = {}

    def add(role, email, pw, name, cats=None):
        u = User(role=role, email=email, password_hash=hash_password(pw), display_name=name)
        db.add(u)
        db.flush()
        for c in cats or []:
            db.add(FacultyCategory(user_id=u.id, category=c))
        staff[email] = u
        return u

    kavya = add("FACULTY", "kavya.raghavan@northfielddemo.edu", "FacultyDemo123!",
                "Dr. Kavya Raghavan", ["TECHNICAL_SKILL", "PROJECT", "CERTIFICATION"])
    add("FACULTY", "rohit.deshmukh@northfielddemo.edu", "FacultyDemo123!",
        "Rohit Deshmukh", ["INTERNSHIP", "ACTIVITY"])
    add("TPO_ADMIN", "meera.iyer@northfielddemo.edu", "TPOAdmin123!", "Meera Iyer")
    db.commit()
    return staff


DEPARTMENTS = [
    ("CSE", "Computer Science & Engineering"),
    ("ISE", "Information Science & Engineering"),
    ("ECE", "Electronics & Communication"),
    ("ME", "Mechanical Engineering"),
    ("CE", "Civil Engineering"),
]


def seed_departments(db: Session) -> dict:
    """Department rows + one department account per department (TPO-provisioned)."""
    depts = {}
    for code, name in DEPARTMENTS:
        d = db.execute(select(Department).where(Department.code == code)).scalars().first()
        if not d:
            d = Department(code=code, name=name)
            db.add(d)
            db.flush()
        depts[code] = d
    for code, name in DEPARTMENTS:
        email = f"dept.{code.lower()}@northfielddemo.edu"
        if not db.execute(select(User).where(User.email == email)).scalars().first():
            db.add(User(role="DEPARTMENT", email=email,
                        password_hash=hash_password("DeptDemo123!"),
                        display_name=f"{name} Office", department_id=depts[code].id))
    db.commit()
    return depts


# Fictional, clearly-demo companies with DIFFERENTiated criteria so the
# matching engine produces genuinely different eligible pools.
COMPANY_DEFS = [
    dict(
        name="VerveTech Solutions", industry="Software Products", location="Bengaluru",
        website="https://vervetech-demo.example", description="Demo software-product company.",
        recruiter_email="priya.nair@vervetech-demo.example", recruiter_name="Priya Nair (Recruiter)",
        drives=[dict(
            title="Full-Stack Developer — Summer Placement Drive", role="Full-Stack Developer",
            job_description="Design, build and ship web features end-to-end (React + Node/Python + PostgreSQL).",
            location="Bengaluru", employment_type="Full-time", drive_date="2026-10-15",
            deadline="2026-10-05", open_positions=8, ctc=None,
            min_cgpa=7.0, min_coding=65.0, min_communication=55.0, project_required=True,
            target_branches=None, eligible_semesters=[6, 8],
            required_skills=["JAVASCRIPT", "REACT", "BACKEND", "SQL"],
            preferred_skills=["GIT", "CLOUD"], preferred_career_code="FULL_STACK")]),
    dict(
        name="DataBridge Analytics", industry="Data & Business Intelligence", location="Remote (India)",
        website="https://databridge-demo.example", description="Demo data analytics company.",
        recruiter_email="arjun.kulkarni@databridge-demo.example", recruiter_name="Arjun Kulkarni (Recruiter)",
        drives=[dict(
            title="Data Analyst — New Grad Drive", role="Data Analyst",
            job_description="Clean, model and visualise operational data; build SQL-backed dashboards.",
            location="Remote (India)", employment_type="Full-time", drive_date="2026-10-20",
            deadline="2026-10-08", open_positions=6, ctc=None,
            min_cgpa=6.5, min_aptitude=60.0, min_coding=40.0, project_required=False,
            target_branches=None, eligible_semesters=[6, 8],
            required_skills=["SQL", "PYTHON"],
            preferred_skills=["PANDAS", "EXCEL"], preferred_career_code="DATA_ANALYST")]),
    dict(
        name="CodeForge Systems", industry="Core Engineering", location="Hyderabad",
        website="https://codeforge-demo.example", description="Demo core-engineering company (coding-focused).",
        recruiter_email="sneha.reddy@codeforge-demo.example", recruiter_name="Sneha Reddy (Recruiter)",
        drives=[dict(
            title="Software Engineer (Coding & DSA) — Placement", role="Software Engineer",
            job_description="Systems-oriented problem solving; strong fundamentals in DSA and Python.",
            location="Hyderabad", employment_type="Full-time", drive_date="2026-10-18",
            deadline="2026-10-06", open_positions=10, ctc=None,
            min_cgpa=7.5, min_coding=75.0, min_aptitude=65.0, project_required=False,
            target_branches=None, eligible_semesters=[6, 8],
            required_skills=["CODING", "DSA", "PYTHON"],
            preferred_skills=["LOGICAL"], preferred_career_code=None)]),
    dict(
        name="Meridian Infra", industry="Infrastructure & Cloud", location="Pune",
        website="https://meridian-demo.example", description="Demo infrastructure company (skill-first).",
        recruiter_email="vikram.shah@meridian-demo.example", recruiter_name="Vikram Shah (Recruiter)",
        drives=[dict(
            title="Cloud Support Engineer — Placement", role="Cloud Support Engineer",
            job_description="Skill-first: cloud basics, Git workflows and clear communication. No strict CGPA gate.",
            location="Pune", employment_type="Full-time", drive_date="2026-10-22",
            deadline="2026-10-10", open_positions=5, ctc=None,
            min_readiness=50.0, min_communication=50.0, project_required=False,
            target_branches=None, eligible_semesters=None,
            required_skills=["CLOUD", "GIT"],
            preferred_skills=["C_CPP"], preferred_career_code=None)]),
    dict(
        name="Pinnacle Consulting", industry="Consulting & Analytics", location="Bengaluru",
        website="https://pinnacle-demo.example", description="Demo consulting firm (academics + communication focused).",
        recruiter_email="divya.menon@pinnacle-demo.example", recruiter_name="Divya Menon (Recruiter)",
        drives=[dict(
            title="Business Analyst — Consulting Track", role="Business Analyst",
            job_description="Client-facing analysis; strong academics and communication are weighted highly.",
            location="Bengaluru", employment_type="Full-time", drive_date="2026-10-25",
            deadline="2026-10-12", open_positions=4, ctc=None,
            min_cgpa=8.0, min_tenth=75.0, min_communication=70.0, project_required=False,
            target_branches=None, eligible_semesters=None,
            required_skills=[],
            preferred_skills=["EXCEL", "PANDAS", "PRESENTATION"], preferred_career_code=None)]),
    dict(
        name="BrightPath Learning", industry="EdTech", location="Bengaluru",
        website="https://brightpath-demo.example", description="Demo ed-tech company (front-end, lower entry bar).",
        recruiter_email="ishaan.gupta@brightpath-demo.example", recruiter_name="Ishaan Gupta (Recruiter)",
        drives=[dict(
            title="Front-End Developer Intern → Pre-Placement Offer", role="Front-End Developer",
            job_description="Front-end intern with PPO. Lower entry bar; strong fundamentals in web tech.",
            location="Bengaluru", employment_type="Internship → Full-time", drive_date="2026-10-16",
            deadline="2026-10-04", open_positions=6, ctc=None,
            min_readiness=40.0, min_coding=45.0, project_required=False,
            target_branches=None, eligible_semesters=[4, 6],
            required_skills=["JAVASCRIPT", "HTML_CSS"],
            preferred_skills=["REACT"], preferred_career_code="FULL_STACK")]),
]


def seed_companies(db: Session, staff: dict) -> list[dict]:
    """Fictional demo companies + recruiter accounts + open drives."""
    tpo = staff["meera.iyer@northfielddemo.edu"]
    out = []
    for cd in COMPANY_DEFS:
        c = db.execute(select(Company).where(Company.name == cd["name"])).scalars().first()
        if not c:
            c = Company(name=cd["name"], industry=cd["industry"], location=cd["location"],
                        website=cd["website"], description=cd["description"],
                        status="ACTIVE", created_by=tpo.id)
            db.add(c)
            db.flush()
        if cd["recruiter_email"] and not db.execute(
                select(User).where(User.email == cd["recruiter_email"])).scalars().first():
            db.add(User(role="COMPANY", email=cd["recruiter_email"],
                        password_hash=hash_password("RecruiterDemo123!"),
                        display_name=cd["recruiter_name"], company_id=c.id))
        for drv in cd["drives"]:
            exists = db.execute(select(PlacementDrive).where(
                PlacementDrive.company_id == c.id,
                PlacementDrive.title == drv["title"])).scalars().first()
            if not exists:
                d = PlacementDrive(company_id=c.id, status="OPEN", created_by=tpo.id, **drv)
                db.add(d)
        out.append({"company_id": c.id, "name": c.name})
    db.commit()
    return out


def preassign_verification(db: Session, staff: dict) -> int:
    """TPO routes some PENDING requests to the verifiers (demo of oversight)."""
    tpo = staff["meera.iyer@northfielddemo.edu"]
    reqs = db.execute(select(VerificationRequest).where(
        VerificationRequest.status == "PENDING")).scalars().all()
    assigned = 0
    kavya = staff.get("kavya.raghavan@northfielddemo.edu")
    rohit = staff.get("rohit.deshmukh@northfielddemo.edu")

    def cats_of(u):
        return {c.category for c in db.execute(
            select(FacultyCategory).where(FacultyCategory.user_id == u.id)).scalars()}

    kavya_cats = cats_of(kavya)
    rohit_cats = cats_of(rohit)
    for i, r in enumerate(reqs):
        # category-aware routing: verifier must cover the request's category
        if r.category in kavya_cats:
            target = kavya
        elif r.category in rohit_cats:
            target = rohit
        else:
            target = kavya if i % 2 == 0 else rohit
        a = db.execute(select(VerificationAssignment).where(
            VerificationAssignment.request_id == r.id)).scalars().first()
        if a:
            a.verifier_id = target.id
            a.status = "PENDING"
        else:
            db.add(VerificationAssignment(request_id=r.id, verifier_id=target.id,
                                          assigned_by=tpo.id))
        assigned += 1
    db.commit()
    return assigned


def _skill_rows(db: Session, student_id: int, rng: random.Random, f: dict, tech_latent: float) -> dict:
    """Create student skill rows. Returns {code: row} for derived features."""
    rows: dict[str, object] = {}
    skills = {s.code: s for s in db.execute(select(Skill)).scalars().all()}

    def add_skill(code, score, source, status, claimed=None):
        row = StudentSkill(student_id=student_id, skill_id=skills[code].id, claimed_level=claimed,
                           score=None if score is None else round(float(score)),
                           source=source, status=status)
        db.add(row)
        rows[code] = row

    # assessment/sourced dimensions (institution-conducted mock assessments)
    for code, feat in [("CODING", "coding_score"), ("APTITUDE", "aptitude_score"),
                       ("LOGICAL", "logical_score"), ("COMMUNICATION", "communication_score"),
                       ("INTERVIEW", "interview_score"), ("PRESENTATION", "presentation_score")]:
        if rng.random() < 0.94:
            add_skill(code, f[feat], "ASSESSMENT", "VERIFIED")

    def tech(code, base, presence=0.72):
        if code in rows:
            return
        r = rng.random()
        if r < presence:
            add_skill(code, base, "ASSESSMENT", "VERIFIED")
        elif r < presence + 0.10:
            lvl = "Advanced" if base >= 75 else ("Intermediate" if base >= 55 else "Beginner")
            add_skill(code, None, "SELF_REPORTED", "PENDING", claimed=lvl)

    prog, web = f["programming_score"], f["web_dev_score"]
    tech("PYTHON", prog + rng.gauss(0, 5))
    tech("JAVA", prog * 0.85 + 10 + rng.gauss(0, 5), presence=0.5)
    tech("C_CPP", prog * 0.8 + 5 + rng.gauss(0, 5), presence=0.45)
    tech("JAVASCRIPT", web * 0.6 + prog * 0.4 + rng.gauss(0, 5))
    tech("HTML_CSS", web * 0.7 + 15 + rng.gauss(0, 5), presence=0.6)
    tech("REACT", web * 0.6 + 10 + rng.gauss(0, 6), presence=0.55)
    tech("NODE_JS", web * 0.55 + 10 + rng.gauss(0, 6), presence=0.45)
    tech("BACKEND", web * 0.5 + prog * 0.3 + 8 + rng.gauss(0, 5), presence=0.55)
    tech("REST_API", web * 0.5 + 12 + rng.gauss(0, 5), presence=0.4)
    add_skill("SQL", f["sql_score"], "ASSESSMENT", "VERIFIED")
    add_skill("DSA", f["dsa_score"], "ASSESSMENT", "VERIFIED")
    add_skill("GIT", f["git_score"], "ASSESSMENT", "VERIFIED")
    add_skill("CLOUD", f["cloud_score"], "ASSESSMENT", "VERIFIED")
    tech("PANDAS", prog * 0.6 + 10 + rng.gauss(0, 5), presence=0.4)
    tech("STATISTICS", 55 + 10 * (f["aptitude_score"] - 50) / 25 + rng.gauss(0, 5), presence=0.4)
    tech("EXCEL", 50 + (f["tenth_percentage"] - 50) / 3 + rng.gauss(0, 5), presence=0.4)
    tech("POWER_BI", 45 + (f["aptitude_score"] - 50) / 4 + rng.gauss(0, 5), presence=0.3)
    db.flush()
    return rows


def _complexity(rng: random.Random, practical: float) -> str:
    r = rng.random() + practical * 0.15
    return "Advanced" if r > 0.78 else ("Intermediate" if r > 0.45 else "Basic")


def seed_students(db: Session, staff: dict) -> list[dict]:
    rng = random.Random(SEED)
    random.seed(SEED)
    np_seed_profiles = gd.generate_master(seed=gd.MASTER_SEED)[1]

    tpo = staff["meera.iyer@northfielddemo.edu"]
    job = ImportJob(file_name="institution_master_demo.csv", uploaded_by=tpo.id, status="IMPORTED",
                    rows_detected=600, valid_rows=600, update_rows=600, rejected_rows=0)
    db.add(job)
    db.flush()

    demo_students = []
    for p in np_seed_profiles:
        usn, branch, sem = p["usn"], p["branch"], p["semester"]
        name = p["name"]
        fn = name.split()[0]
        student = Student(usn=usn, branch=branch, semester=sem)
        db.add(student)
        db.flush()
        user = User(role="STUDENT", email=f"{usn.lower()}@northfielddemo.edu", display_name=name)
        db.add(user)
        db.flush()
        student.user_id = user.id
        db.add(AcademicRecord(
            student_id=student.id, cgpa=p["features"]["cgpa"],
            tenth_percentage=p["features"]["tenth_percentage"],
            twelfth_percentage=p["features"]["twelfth_percentage"],
            backlog_history_count=p["features"]["backlog_history_count"],
            source_import_id=job.id,
        ))
        _skill_rows(db, student.id, rng, p["features"], p["technical"])

        f = p["features"]
        # projects
        n_ver = f["verified_project_count"]
        for i in range(n_ver):
            c = _complexity(rng, p["practical"])
            db.add(Project(student_id=student.id, title=rng.choice(PROJECT_TITLES),
                           description="Semester project with a working demo and documented architecture.",
                           tech_stack=rng.choice(PROJECT_STACKS), project_type="Academic",
                           team_type="Team" if rng.random() < 0.6 else "Individual",
                           student_role=rng.choice(["Backend Developer", "Frontend Developer", "Full-Stack Developer", "Team Lead"]),
                           claimed_complexity=c, verified_complexity=c,
                           github_url=f"https://github.com/{fn.lower()}/{usn.lower()}-proj{i}",
                           status="VERIFIED"))
        if n_ver == 0 and rng.random() < 0.25:
            db.add(Project(student_id=student.id, title=rng.choice(PROJECT_TITLES),
                           tech_stack=rng.choice(PROJECT_STACKS), project_type="Personal", team_type="Individual",
                           student_role="Developer", claimed_complexity="Basic", status="PENDING"))
        # internships
        for i in range(f["verified_internship_count"]):
            org, role = rng.choice(INTERNSHIP_ORGS)
            db.add(Internship(student_id=student.id, organization=org, role=role,
                              domain=rng.choice(["Backend", "Data", "Cloud", "Frontend"]),
                              start_date="2025-01-06", end_date="2025-04-04",
                              description="Industry internship with a mentor-reviewed report.", status="VERIFIED"))
        if f["verified_internship_count"] == 0 and rng.random() < 0.12:
            org, role = rng.choice(INTERNSHIP_ORGS)
            db.add(Internship(student_id=student.id, organization=org, role=role,
                              domain="Backend", start_date="2025-05-01", end_date="2025-07-31",
                              description="Summer internship claim (proof attached).", status="PENDING"))
        # certifications
        for i in range(f["verified_certification_count"]):
            nm, issuer, cat = rng.choice(CERT_POOL)
            db.add(Certification(student_id=student.id, name=nm, issuer=issuer,
                                 credential_id=f"CRD{rng.randint(100000, 999999)}",
                                 issue_date=f"2025-{rng.randint(1, 12):02d}-15", skill_category=cat,
                                 status="VERIFIED"))
        if rng.random() < 0.15:
            nm, issuer, cat = rng.choice(CERT_POOL)
            db.add(Certification(student_id=student.id, name=nm, issuer=issuer,
                                 credential_id=f"CRD{rng.randint(100000, 999999)}",
                                 issue_date=f"2025-{rng.randint(1, 12):02d}-10", skill_category=cat,
                                 status="PENDING"))
        # activities
        if f["hackathon_score"] > 0 or f["leadership_score"] > 0:
            nm, et, ach = rng.choice(ACTIVITIES_POOL)
            db.add(Activity(student_id=student.id, event_name=nm, event_type=et, organizer="Institute",
                            event_date="2025-09-20", role=rng.choice(["Participant", "Team Lead", "Organizer"]),
                            achievement=ach, status="VERIFIED" if rng.random() < 0.6 else "PENDING"))
        # open source
        if f["open_source_score"] > 0:
            url, desc = rng.choice(OSS_REPOS)
            db.add(OpenSource(student_id=student.id, repository_url=url, contribution_type="Code + Docs",
                              description=desc, status="VERIFIED" if rng.random() < 0.5 else "PENDING"))
        # explicit none declarations
        if n_ver == 0 and rng.random() < 0.7:
            student.no_projects_declared = True
        if f["verified_internship_count"] == 0 and rng.random() < 0.6:
            student.no_internships_declared = True
        if f["verified_certification_count"] == 0 and rng.random() < 0.5:
            student.no_certifications_declared = True

        demo_students.append({"usn": usn, "name": name})
    db.commit()

    # every pending self-owned entity gets a VerificationRequest so the
    # faculty queue and student passport always agree
    entity_map = {
        "project": (Project, "PROJECT"),
        "internship": (Internship, "INTERNSHIP"),
        "certification": (Certification, "CERTIFICATION"),
        "activity": (Activity, "ACTIVITY"),
        "open_source": (OpenSource, "ACTIVITY"),
    }
    for etype, (model, category) in entity_map.items():
        for obj in db.execute(select(model).where(model.status == "PENDING")).scalars():
            exists = db.execute(select(VerificationRequest).where(
                VerificationRequest.student_id == obj.student_id,
                VerificationRequest.entity_type == etype,
                VerificationRequest.entity_id == obj.id)).scalars().first()
            if not exists:
                db.add(VerificationRequest(student_id=obj.student_id, entity_type=etype,
                                           entity_id=obj.id, category=category,
                                           status="PENDING"))
    db.commit()
    return demo_students


def craft_primary_demo(db: Session) -> Student:
    """Aarav Mehta — the primary live-demo student (near-Ready with SQL/communication
    gaps and one pending project awaiting faculty verification)."""
    skills = {s.code: s for s in db.execute(select(Skill)).scalars().all()}
    student = Student(usn="3PM24CS500", branch="CSE", semester=6, no_internships_declared=True,
                      no_certifications_declared=False, target_career_code="FULL_STACK")
    db.add(student)
    db.flush()
    user = User(role="STUDENT", email="3pm24cs500@northfielddemo.edu", display_name="Aarav Mehta")
    db.add(user)
    db.flush()
    student.user_id = user.id
    db.add(AcademicRecord(student_id=student.id, cgpa=7.86, tenth_percentage=82.3,
                          twelfth_percentage=80.6, backlog_history_count=0))

    def sk(code, score, source, status, claimed=None):
        db.add(StudentSkill(student_id=student.id, skill_id=skills[code].id, claimed_level=claimed,
                            score=score, source=source, status=status))

    for code, score in [("CODING", 64), ("APTITUDE", 61), ("LOGICAL", 62), ("COMMUNICATION", 49),
                        ("INTERVIEW", 54), ("PRESENTATION", 56), ("SQL", 44), ("DSA", 61),
                        ("PYTHON", 69), ("JAVASCRIPT", 64), ("HTML_CSS", 66), ("REACT", 52),
                        ("BACKEND", 48), ("GIT", 72), ("CLOUD", 41)]:
        sk(code, score, "ASSESSMENT", "VERIFIED")

    db.add(Project(student_id=student.id, title="Campus Events Portal",
                   description="Full-stack portal for managing college events with registration and analytics.",
                   tech_stack=["React", "Node.js", "PostgreSQL"], project_type="Academic", team_type="Team",
                   student_role="Full-Stack Developer", claimed_complexity="Intermediate",
                   verified_complexity="Intermediate",
                   github_url="https://github.com/aaravmehta/campus-events-portal", status="VERIFIED"))
    proj = Project(student_id=student.id, title="Inventory Management Web App",
                   description="REST API + dashboard for small-business inventory with JWT auth, Postgres, and reports.",
                   tech_stack=["React", "FastAPI", "PostgreSQL"], project_type="Personal", team_type="Individual",
                   student_role="Full-Stack Developer", claimed_complexity="Advanced",
                   github_url="https://github.com/aaravmehta/inventory-web-app", status="PENDING")
    db.add(proj)
    db.flush()
    pdf = make_simple_pdf("Project Summary — Inventory Management Web App", [
        "Student: Aarav Mehta (3PM24CS500), CSE, Semester 6",
        "Role: Full-Stack Developer (individual project)",
        "Stack: React (frontend), FastAPI (REST API), PostgreSQL (database)",
        "Features: JWT authentication, CRUD inventory, stock alerts, CSV export.",
        "Complexity claimed: Advanced (auth, REST API, relational DB, reporting)",
        "Synthetic demo evidence generated for the CareerDNA hackathon prototype.",
    ])
    save_evidence(student.id, "project", proj.id, "inventory-project-summary.pdf", pdf,
                  "application/pdf", db)
    db.add(Certification(student_id=student.id, name="AWS Cloud Practitioner", issuer="Amazon Web Services",
                         credential_id="CRD550121", issue_date="2025-08-15", skill_category="CLOUD",
                         status="VERIFIED"))
    db.add(Activity(student_id=student.id, event_name="HackNorth 2026", event_type="Hackathon",
                    organizer="Northfield Institute of Technology", event_date="2026-01-17",
                    role="Team Lead", achievement="Finalist", status="VERIFIED"))
    db.add(VerificationRequest(student_id=student.id, entity_type="project", entity_id=proj.id,
                               category="PROJECT", status="PENDING"))
    db.commit()
    return student


def run_analyses(db: Session) -> int:
    from app.services.analysis_service import run_analysis
    students = db.execute(select(Student).where(Student.is_active == True)).scalars().all()  # noqa: E712
    count = 0
    for s in students:
        try:
            if run_analysis(db, s, reason="seed"):
                count += 1
        except Exception as e:  # keep seeding resilient
            print(f"  analysis skipped for {s.usn}: {e}")
    db.commit()
    return count


def main(analysis: bool = True, demo_students: bool = False) -> None:
    """Wipe + reseed.

    demo_students=False (default)  -> empty institution: reference data + staff only.
                                       Import your own students via the TPO CSV import.
    demo_students=True             -> full synthetic demo roster (600 students,
                                       Aarav flagship, demo accounts).
    """
    Base.metadata.create_all(engine)
    db = SessionLocal()
    clear_all(db)
    print("Seeding reference data (skills, careers, benchmarks, interventions)...")
    seed_reference(db)
    print("Seeding staff accounts...")
    staff = seed_staff(db)
    print("Seeding departments + department accounts...")
    seed_departments(db)
    print("Seeding fictional demo companies + drives...")
    seed_companies(db, staff)
    if demo_students:
        print("Generating 600 synthetic students with evidence + verification states...")
        seed_students(db, staff)
        print("Crafting primary demo student (Aarav Mehta, 3PM24CS500)...")
        craft_primary_demo(db)
    else:
        print("No synthetic students (empty institution — import your own CSV via the TPO page).")

    if analysis and demo_students:
        model_path = BASE / "artifacts" / "placement_readiness_model.joblib"
        if model_path.exists():
            from app.services.model_service import model_service
            if not model_service.available and not model_service.load():
                print(f"WARNING: model could not be loaded: {model_service.error}")
            else:
                print(f"Running readiness analysis for all eligible students "
                      f"(model {model_service.version})...")
                n = run_analyses(db)
                print(f"  {n} students analyzed.")
        else:
            print("WARNING: model artifact not found — analysis skipped. Run: python -m scripts.train_model")

    if demo_students:
        n_assign = preassign_verification(db, staff)
        print(f"  TPO pre-assigned {n_assign} verification requests to verifiers.")

    # demo accounts report (secondary demo students picked deterministically
    # from the analyzed cohort: Ready ~85, Needs Training ~48)
    def _pick_student(category: str, target: float) -> dict | None:
        rows = db.execute(
            select(Prediction, Student, User)
            .join(Student, Prediction.student_id == Student.id)
            .join(User, Student.user_id == User.id)
            .where(Prediction.is_current == True,  # noqa: E712
                   Prediction.category == category,
                   Prediction.profile_trust >= 70)).all()
        if not rows:
            return None
        best = min(rows, key=lambda r: abs(r[0].probability * 100 - target))
        return {"usn": best[1].usn, "name": best[2].display_name,
                "email": best[2].email, "branch": best[1].branch,
                "semester": best[1].semester,
                "readiness": round(best[0].probability * 100, 1), "category": category}

    accounts = {
        "faculty_technical": {"email": "kavya.raghavan@northfielddemo.edu", "password": "FacultyDemo123!",
                              "name": "Dr. Kavya Raghavan", "categories": ["TECHNICAL_SKILL", "PROJECT", "CERTIFICATION"]},
        "faculty_ops": {"email": "rohit.deshmukh@northfielddemo.edu", "password": "FacultyDemo123!",
                        "name": "Rohit Deshmukh", "categories": ["INTERNSHIP", "ACTIVITY"]},
        "tpo_admin": {"email": "meera.iyer@northfielddemo.edu", "password": "TPOAdmin123!",
                      "name": "Meera Iyer"},
        "department_cse": {"email": "dept.cse@northfielddemo.edu", "password": "DeptDemo123!",
                           "name": "CSE Office"},
        "department_ise": {"email": "dept.ise@northfielddemo.edu", "password": "DeptDemo123!",
                           "name": "ISE Office"},
        "recruiter_verve": {"email": "priya.nair@vervetech-demo.example",
                            "password": "RecruiterDemo123!", "name": "Priya Nair (VerveTech)"},
        "demo_otp": "246810",
        "student_note": ("Log in with any imported USN + the demo OTP",
                         "Demo student roster available with: python -m scripts.seed_demo --demo"),
    }
    if demo_students:
        accounts["primary_student"] = {"usn": "3PM24CS500", "name": "Aarav Mehta",
                                       "email": "3pm24cs500@northfielddemo.edu",
                                       "note": "Near-Ready flagship: one VERIFIED project + one PENDING project "
                                               "(faculty verification queue), SQL & communication gaps, target FULL_STACK."}
        accounts["ready_demo_student"] = _pick_student("READY", 85)
        accounts["needs_training_demo_student"] = _pick_student("NEEDS_TRAINING", 48)
    (BASE / "artifacts" / "demo_accounts.json").write_text(json.dumps(accounts, indent=2))
    print("Seed complete.")
    db.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Seed the CareerDNA demo database.")
    ap.add_argument("--demo", action="store_true",
                    help="seed the full synthetic student roster (default: empty institution)")
    ap.add_argument("--no-analysis", action="store_true", help="skip running readiness analysis")
    args = ap.parse_args()
    main(analysis=not args.no_analysis, demo_students=args.demo)
