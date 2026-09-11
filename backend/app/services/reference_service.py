"""Reference data bootstrap (idempotent): skills, career tracks,
benchmarks, interventions. Called at app startup and by the seed script.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import CareerBenchmark, CareerTrack, Intervention, Skill

SKILLS = [
    # code, name, category, general benchmark
    ("PYTHON", "Python", "PROGRAMMING", 70),
    ("JAVA", "Java", "PROGRAMMING", 70),
    ("JAVASCRIPT", "JavaScript", "WEB", 70),
    ("C_CPP", "C/C++", "PROGRAMMING", 70),
    ("SQL", "SQL", "DATA", 70),
    ("DSA", "DSA & Problem Solving", "CS_CORE", 65),
    ("HTML_CSS", "HTML/CSS", "WEB", 65),
    ("REACT", "React", "WEB", 70),
    ("NODE_JS", "Node.js", "WEB", 70),
    ("BACKEND", "Backend Development", "WEB", 70),
    ("REST_API", "REST APIs", "WEB", 70),
    ("GIT", "Git/GitHub", "TOOLS", 65),
    ("CLOUD", "Cloud Fundamentals", "TOOLS", 55),
    ("APTITUDE", "Aptitude", "ASSESSMENT", 70),
    ("LOGICAL", "Logical Reasoning", "ASSESSMENT", 70),
    ("CODING", "Coding Assessment", "ASSESSMENT", 70),
    ("COMMUNICATION", "Communication", "EXPERIENCE", 65),
    ("INTERVIEW", "Interview Performance", "EXPERIENCE", 70),
    ("PRESENTATION", "Presentation", "EXPERIENCE", 65),
]

CAREER_TRACKS = [
    {
        "code": "FULL_STACK",
        "name": "Full-Stack Developer",
        "description": ("End-to-end product development: frontend interfaces, backend services, "
                        "databases, and deployment."),
        "benchmarks": [
            # skill_code, target, weight, mandatory
            ("BACKEND", 75, 0.18, True),
            ("JAVASCRIPT", 70, 0.14, True),
            ("REACT", 65, 0.12, False),
            ("NODE_JS", 65, 0.10, False),
            ("SQL", 70, 0.12, True),
            ("PYTHON", 60, 0.08, False),
            ("GIT", 65, 0.08, False),
            ("CODING", 70, 0.08, False),
            ("PROJECT_EXP", 70, 0.10, True),
        ],
    },
    {
        "code": "DATA_ANALYST",
        "name": "Data Analyst",
        "description": ("Business intelligence: data extraction, analysis with Python/SQL, "
                        "statistical reasoning, and insight communication."),
        "benchmarks": [
            ("SQL", 80, 0.20, True),
            ("PYTHON", 70, 0.16, True),
            ("DSA", 60, 0.10, False),
            ("CODING", 65, 0.10, False),
            ("APTITUDE", 70, 0.10, False),
            ("LOGICAL", 65, 0.08, False),
            ("COMMUNICATION", 70, 0.10, True),
            ("PRESENTATION", 60, 0.06, False),
            ("PROJECT_EXP", 65, 0.10, True),
        ],
    },
]

INTERVENTIONS = [
    {"code": "SQL_BOOTCAMP", "name": "SQL Foundations Bootcamp", "skills": ["SQL"],
     "feature_deltas": {"sql_score": 1.0}, "estimated_weeks": 4, "career_relevance": 0.8,
     "description": "Structured 4-week SQL track: querying, joins, aggregation, and a mini capstone."},
    {"code": "DSA_SPRINT", "name": "DSA Problem-Solving Sprint", "skills": ["DSA", "CODING"],
     "feature_deltas": {"dsa_score": 1.0, "coding_score": 0.6}, "estimated_weeks": 6,
     "career_relevance": 0.85,
     "description": "6-week daily problem sets with pattern-based revision and timed mock assessments."},
    {"code": "COMM_WORKSHOP", "name": "Communication & Interview Workshop", "skills": ["COMMUNICATION", "INTERVIEW", "PRESENTATION"],
     "feature_deltas": {"communication_score": 1.0, "interview_score": 0.7, "presentation_score": 0.5},
     "estimated_weeks": 3, "career_relevance": 0.7,
     "description": "3-week workshop: structured answering, mock interviews, and technical presentations."},
    {"code": "FULLSTACK_SPRINT", "name": "Applied Full-Stack Sprint", "skills": ["JAVASCRIPT", "BACKEND", "NODE_JS", "REACT", "GIT"],
     "feature_deltas": {"web_dev_score": 1.0, "git_score": 0.5}, "estimated_weeks": 6,
     "career_relevance": 0.8,
     "description": "6-week project sprint building a full-stack application with Git-based collaboration."},
    {"code": "DATA_SPRINT", "name": "Data Analysis Sprint", "skills": ["SQL", "PYTHON", "DSA"],
     "feature_deltas": {"sql_score": 0.8, "programming_score": 0.8}, "estimated_weeks": 5,
     "career_relevance": 0.75,
     "description": "5-week Python + SQL data analysis track with a business-case capstone."},
    {"code": "APTITUDE_PROGRAM", "name": "Aptitude & Reasoning Program", "skills": ["APTITUDE", "LOGICAL"],
     "feature_deltas": {"aptitude_score": 1.0, "logical_score": 0.8}, "estimated_weeks": 4,
     "career_relevance": 0.6,
     "description": "4-week daily drills with weekly timed mocks and error-log review."},
    {"code": "GIT_WORKSHOP", "name": "Git & Collaboration Workshop", "skills": ["GIT"],
     "feature_deltas": {"git_score": 1.0}, "estimated_weeks": 2,
     "career_relevance": 0.4,
     "description": "2-week workshop on professional Git workflows, PRs, and CI basics."},
    {"code": "CLOUD_WORKSHOP", "name": "Cloud Fundamentals Workshop", "skills": ["CLOUD"],
     "feature_deltas": {"cloud_score": 1.0}, "estimated_weeks": 3,
     "career_relevance": 0.4,
     "description": "3-week fundamentals track ending in one free-tier deployment."},
]


def ensure_reference_data(db: Session | None = None) -> None:
    close = False
    if db is None:
        db = SessionLocal()
        close = True
    try:
        for code, name, category, benchmark in SKILLS:
            exists = db.execute(select(Skill).where(Skill.code == code)).scalars().first()
            if not exists:
                db.add(Skill(code=code, name=name, category=category,
                             general_benchmark=benchmark))
        for track in CAREER_TRACKS:
            exists = db.execute(select(CareerTrack).where(
                CareerTrack.code == track["code"])).scalars().first()
            if not exists:
                db.add(CareerTrack(code=track["code"], name=track["name"],
                                   description=track["description"], active=True))
                for skill_code, target, weight, mandatory in track["benchmarks"]:
                    db.add(CareerBenchmark(career_code=track["code"], skill_code=skill_code,
                                           target_score=target, importance_weight=weight,
                                           mandatory=mandatory))
        for iv in INTERVENTIONS:
            exists = db.execute(select(Intervention).where(
                Intervention.code == iv["code"])).scalars().first()
            if not exists:
                db.add(Intervention(
                    code=iv["code"], name=iv["name"], skill_codes=iv["skills"],
                    feature_deltas=iv["feature_deltas"], estimated_weeks=iv["estimated_weeks"],
                    career_relevance=iv["career_relevance"], description=iv["description"],
                    active=True))
        db.commit()
    finally:
        if close:
            db.close()
