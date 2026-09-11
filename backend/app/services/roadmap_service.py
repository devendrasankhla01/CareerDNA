"""Roadmap engine: turns optimizer-selected actions into structured phases.

Templates are curated per skill band and target career; content is
deterministic (zero LLM dependency) and driven by the student's actual
gap values.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Roadmap, RoadmapItem, Student
from app.services.optimizer_service import optimize

TEMPLATES: dict[str, dict] = {
    "sql_score": {
        "phase": "SQL Foundations",
        "goal": "Move from ad-hoc queries to confident relational modelling.",
        "tasks": [
            "Complete a structured module: SELECT, WHERE, ORDER BY, GROUP BY",
            "Work through 15 JOIN exercises (inner, left, self-joins)",
            "Practise aggregation and subqueries on a sample database",
            "Apply SQL to a small CRUD project with real data",
        ],
        "milestone": "Retake the SQL verification assessment at 70+ and ship one database-backed feature.",
    },
    "dsa_score": {
        "phase": "Problem-Solving Sprint",
        "goal": "Build repeatable problem-solving speed and accuracy.",
        "tasks": [
            "Daily sets of 2–3 problems across arrays, strings, and hash maps",
            "Learn and apply the top 10 patterns (two pointers, sliding window, BFS/DFS)",
            "Timed 45-minute practice rounds with self-review of mistakes",
        ],
        "milestone": "Improve coding assessment score and solve 40+ problems with written approaches.",
    },
    "programming_score": {
        "phase": "Programming Fundamentals",
        "goal": "Strengthen core language fluency and clean implementation habits.",
        "tasks": [
            "Refactor one existing project module for clarity and testability",
            "Complete 20 structured exercises on core data structures",
            "Add unit tests to a small library and run them in CI-style locally",
        ],
        "milestone": "Pass a programming assessment improvement target with cleaner, tested code.",
    },
    "web_dev_score": {
        "phase": "Web Development Depth",
        "goal": "Ship production-quality frontend/backend work.",
        "tasks": [
            "Build a REST API with authentication and database integration",
            "Implement one responsive frontend flow with a component library",
            "Deploy the app with environment configuration and basic monitoring",
        ],
        "milestone": "Submit one verified role-relevant web project for faculty review.",
    },
    "git_score": {
        "phase": "Git & Collaboration Workflows",
        "goal": "Use version control like a professional team member.",
        "tasks": [
            "Practise branching, merging, and resolving conflicts",
            "Create pull requests with meaningful reviews on a shared repo",
            "Set up a small CI workflow that runs tests on push",
        ],
        "milestone": "One repository demonstrating clean history, PRs, and CI.",
    },
    "cloud_score": {
        "phase": "Cloud Fundamentals",
        "goal": "Understand core cloud concepts and deploy one workload.",
        "tasks": [
            "Study compute, storage, and networking fundamentals",
            "Deploy one application to a free-tier cloud environment",
            "Document infrastructure and cost basics in a short read-me",
        ],
        "milestone": "One documented cloud deployment of a project you built.",
    },
    "aptitude_score": {
        "phase": "Aptitude Preparation",
        "goal": "Raise quantitative and speed performance.",
        "tasks": [
            "Daily 20-minute quantitative drills (percentages, ratios, probability)",
            "Weekly timed mixed mock with error log review",
        ],
        "milestone": "Score target on the institutional aptitude reassessment.",
    },
    "logical_score": {
        "phase": "Logical Reasoning Practice",
        "goal": "Improve structured reasoning under time pressure.",
        "tasks": [
            "Practice sequence, syllogism, and data-interpretation sets",
            "Review every missed question with the reasoning rule",
        ],
        "milestone": "Improve logical reasoning assessment score by a meaningful margin.",
    },
    "coding_score": {
        "phase": "Coding Assessment Intensive",
        "goal": "Convert practice into consistent assessment performance.",
        "tasks": [
            "Timed practice on the same question families as the assessment",
            "Write and run test cases before submitting solutions",
            "Mock assessment review with a focus on partial credit",
        ],
        "milestone": "Retake the coding assessment at the target score.",
    },
    "communication_score": {
        "phase": "Interview Communication",
        "goal": "Communicate impact clearly in interviews and reviews.",
        "tasks": [
            "Structure every answer with the STAR method",
            "Prepare a 3-minute project walkthrough and record it",
            "Do 2–3 mock interviews with structured feedback",
        ],
        "milestone": "Mock interview reassessment at the target communication score.",
    },
    "interview_score": {
        "phase": "Mock Interview Series",
        "goal": "Build interview-day composure and technique.",
        "tasks": [
            "Two full-length mock interviews (technical + HR)",
            "Write down the top 10 follow-up questions and prepare answers",
            "Refine project explanation for depth and trade-offs",
        ],
        "milestone": "Interview reassessment at the target score.",
    },
    "presentation_score": {
        "phase": "Presentation Practice",
        "goal": "Present technical work with structure and confidence.",
        "tasks": [
            "Prepare and deliver one 8-minute technical presentation",
            "Practice with peer feedback on structure and pacing",
        ],
        "milestone": "Deliver the presentation and capture feedback notes.",
    },
    "verified_project_count": {
        "phase": "Applied Project",
        "goal": "Complete and verify one role-relevant project.",
        "tasks": [
            "Scope a project with a clear problem, data, and outcome",
            "Build core features over 2–3 weeks with regular commits",
            "Write a short project summary and prepare a demo",
        ],
        "milestone": "Submit the project with documentation for faculty verification.",
    },
    "verified_internship_count": {
        "phase": "Industry Exposure Readiness",
        "goal": "Prepare for and pursue practical industry exposure.",
        "tasks": [
            "Polish project evidence and a one-page experience summary",
            "Prepare targeted applications for 3–5 relevant openings",
            "Practise internship-focused interview questions",
        ],
        "milestone": "Secure or document an internship/apprenticeship opportunity (longer-term action).",
    },
}


def generate(db: Session, student: Student, target_type: str = "GENERAL_READINESS",
             career_code: str | None = None) -> dict:
    opt = optimize(db, student, target_type=target_type, career_code=career_code)
    if opt.get("status") != "ok":
        return {"status": opt.get("status", "error")}

    from app.models import Roadmap as RM
    for r in db.execute(select(RM).where(RM.student_id == student.id, RM.is_current == True)).scalars():  # noqa: E712
        r.is_current = False

    if not opt["actions"]:
        db.commit()
        return {"status": "ok", "roadmap": None, "optimizer": opt,
                "message": opt.get("message", "No actions required.")}

    roadmap = Roadmap(
        student_id=student.id,
        target_type=target_type,
        target_value=career_code,
        current_readiness=opt["baseline_readiness"],
        target_readiness=opt["target"],
        estimated_duration=opt["estimated_duration"],
        status="CURRENT",
        is_current=True,
    )
    db.add(roadmap)
    db.flush()

    for i, action in enumerate(opt["actions"], start=1):
        tpl = TEMPLATES.get(action["feature"], TEMPLATES.get("programming_score"))
        start = int(action["current_value"]) if action["current_value"] is not None else 0
        target = int(action["target_value"])
        item = RoadmapItem(
            roadmap_id=roadmap.id, seq=i, phase=tpl["phase"],
            title=f"{action['label']} ({start} → {target})",
            description=tpl["goal"], feature_target=action["feature"],
            starting_value=str(start), target_value=str(target),
            estimated_weeks=action["estimated_weeks"],
            priority="Critical" if i == 1 else ("High" if i == 2 else "Medium"),
            status="NOT_STARTED", tasks_json=tpl["tasks"],
            milestone=tpl["milestone"],
        )
        db.add(item)
    db.commit()

    return {
        "status": "ok",
        "optimizer": opt,
        "roadmap": {
            "id": roadmap.id,
            "target_type": roadmap.target_type,
            "target_value": roadmap.target_value,
            "current_readiness": roadmap.current_readiness,
            "target_readiness": roadmap.target_readiness,
            "estimated_duration": roadmap.estimated_duration,
            "generated_at": roadmap.generated_at.isoformat(),
            "items": [
                {
                    "seq": it.seq, "phase": it.phase, "title": it.title,
                    "description": it.description, "feature_target": it.feature_target,
                    "starting_value": it.starting_value, "target_value": it.target_value,
                    "estimated_weeks": it.estimated_weeks, "priority": it.priority,
                    "status": it.status, "tasks": it.tasks_json or [],
                    "milestone": it.milestone,
                }
                for it in db.execute(select(RoadmapItem).where(
                    RoadmapItem.roadmap_id == roadmap.id).order_by(RoadmapItem.seq)).scalars()
            ],
        },
    }


def latest_roadmap(db: Session, student: Student) -> dict | None:
    r = db.execute(select(Roadmap).where(
        Roadmap.student_id == student.id, Roadmap.is_current == True)).scalars().first()  # noqa: E712
    if not r:
        return None
    items = db.execute(select(RoadmapItem).where(
        RoadmapItem.roadmap_id == r.id).order_by(RoadmapItem.seq)).scalars().all()
    return {
        "id": r.id, "target_type": r.target_type, "target_value": r.target_value,
        "current_readiness": r.current_readiness, "target_readiness": r.target_readiness,
        "estimated_duration": r.estimated_duration, "status": r.status,
        "generated_at": r.generated_at.isoformat(),
        "items": [
            {"id": it.id, "seq": it.seq, "phase": it.phase, "title": it.title,
             "description": it.description, "feature_target": it.feature_target,
             "starting_value": it.starting_value, "target_value": it.target_value,
             "estimated_weeks": it.estimated_weeks, "priority": it.priority,
             "status": it.status, "tasks": it.tasks_json or [], "milestone": it.milestone}
            for it in items
        ],
    }


def update_item_status(db: Session, student: Student, item_id: int, status: str) -> bool:
    if status not in ("NOT_STARTED", "IN_PROGRESS", "COMPLETED"):
        return False
    rm = db.execute(select(Roadmap).where(
        Roadmap.student_id == student.id, Roadmap.is_current == True)).scalars().first()  # noqa: E712
    if not rm:
        return False
    item = db.get(RoadmapItem, item_id)
    if not item or item.roadmap_id != rm.id:
        return False
    item.status = status
    db.commit()
    return True
