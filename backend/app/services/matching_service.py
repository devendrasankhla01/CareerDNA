"""Placement Match Engine — the single two-sided student<->company matcher.

Design (per spec):
  * One engine, two directions: student -> best companies, drive -> best students.
  * Deterministic and explainable — NO second ML model. The existing ML
    readiness score is ONE input (15%), not the whole rule.
  * Eligibility and Match Quality are separate:
      - eligibility = every MANDATORY drive criterion satisfied (hard rules);
      - match_score = weighted alignment (0-100), computed after eligibility.
  * A failed mandatory criterion can never be averaged away.
  * Only verified/trusted profile data is used (unverified self-claims never
    boost a match).
  * Weights are configurable in app.core.config (company_match_weights) and
    documented in docs/methodology.md.
"""
from __future__ import annotations

from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AcademicRecord,
    CareerMatch,
    Internship,
    Project,
    Prediction,
    Skill,
    Student,
    StudentSkill,
)
from app.models import PlacementDrive

SKILL_LABELS = {
    "PYTHON": "Python", "JAVA": "Java", "JAVASCRIPT": "JavaScript", "C_CPP": "C/C++",
    "SQL": "SQL", "DSA": "DSA", "GIT": "Git", "CLOUD": "Cloud", "CODING": "Coding",
    "APTITUDE": "Aptitude", "LOGICAL": "Logical Reasoning", "COMMUNICATION": "Communication",
    "INTERVIEW": "Interview", "PRESENTATION": "Presentation", "REACT": "React",
    "NODE_JS": "Node.js", "BACKEND": "Backend", "REST_API": "REST API", "HTML_CSS": "HTML/CSS",
}

# Criteria the student can realistically improve via upskilling (drives the
# "improvement opportunity" vs "cannot be changed" distinction).
ACTIONABLE_KEYS = {"readiness", "coding", "aptitude", "communication", "project", "internship"}

COMPONENT_LABELS = {
    "required_skills": "Required skill alignment",
    "preferred_skills": "Preferred skill alignment",
    "career": "Career-role alignment",
    "readiness": "Placement readiness",
    "coding_aptitude": "Coding & aptitude alignment",
    "project_internship": "Project & internship alignment",
}


# ---------------------------------------------------------------- inputs
def _load_inputs(db: Session) -> dict[int, dict]:
    """Batch-load everything the engine needs, once, for all active students."""
    students = {
        s.id: s for s in db.execute(
            select(Student).where(Student.is_active == True)).scalars()  # noqa: E712
    }
    inputs: dict[int, dict] = {}
    for sid in students:
        inputs[sid] = {
            "cgpa": None, "tenth": None, "twelfth": None, "backlogs": None,
            "skills": {},  # code -> trusted score
            "verified_projects": 0, "verified_internships": 0,
            "career": {},  # career_code -> match_score
            "readiness": None, "category": None, "profile_version": None,
        }

    for rec in db.execute(select(AcademicRecord)).scalars():
        if rec.student_id in inputs:
            inputs[rec.student_id].update(
                cgpa=rec.cgpa, tenth=rec.tenth_percentage, twelfth=rec.twelfth_percentage,
                backlogs=rec.backlog_history_count)

    for row, skill in db.execute(
            select(StudentSkill, Skill)
            .join(Skill, StudentSkill.skill_id == Skill.id)
            .where(StudentSkill.status == "VERIFIED")).all():
        if row.student_id in inputs and row.score is not None:
            cur = inputs[row.student_id]["skills"].get(skill.code)
            if cur is None or row.score > cur:
                inputs[row.student_id]["skills"][skill.code] = row.score

    for p in db.execute(select(Project).where(Project.status == "VERIFIED")).scalars():
        if p.student_id in inputs:
            inputs[p.student_id]["verified_projects"] += 1
    for i in db.execute(select(Internship).where(Internship.status == "VERIFIED")).scalars():
        if i.student_id in inputs:
            inputs[i.student_id]["verified_internships"] += 1
    for m in db.execute(select(CareerMatch).where(CareerMatch.is_current == True)).scalars():  # noqa: E712
        if m.student_id in inputs:
            cur = inputs[m.student_id]["career"].get(m.career_code, 0)
            if m.match_score > cur:
                inputs[m.student_id]["career"][m.career_code] = m.match_score
    for p in db.execute(select(Prediction).where(Prediction.is_current == True)).scalars():  # noqa: E712
        if p.student_id in inputs:
            inputs[p.student_id]["readiness"] = round(p.probability * 100, 1)
            inputs[p.student_id]["category"] = p.category
    for s in students.values():
        inputs[s.id]["profile_version"] = s.profile_version
    return inputs


# ---------------------------------------------------------------- eligibility
def _check_mandatory(drive: PlacementDrive, inp: dict, st: Student) -> list[dict]:
    """Return the list of FAILED mandatory criteria (empty => eligible)."""
    blockers: list[dict] = []

    def fail(key: str, label: str, required: str, actual: str, actionable: bool):
        blockers.append({"key": key, "label": label, "required": required,
                         "actual": actual, "actionable": actionable})

    a = inp
    if drive.min_cgpa is not None and (a["cgpa"] is None or a["cgpa"] < drive.min_cgpa):
        fail("cgpa", "CGPA", f"≥ {drive.min_cgpa:g}", f"{a['cgpa'] if a['cgpa'] is not None else 'not on file'}", False)
    if drive.min_tenth is not None and (a["tenth"] is None or a["tenth"] < drive.min_tenth):
        fail("tenth", "10th Percentage", f"≥ {drive.min_tenth:g}",
             f"{a['tenth'] if a['tenth'] is not None else 'not on file'}", False)
    if drive.min_twelfth is not None and (a["twelfth"] is None or a["twelfth"] < drive.min_twelfth):
        fail("twelfth", "12th Percentage", f"≥ {drive.min_twelfth:g}",
             f"{a['twelfth'] if a['twelfth'] is not None else 'not on file'}", False)
    if drive.max_backlogs is not None and (a["backlogs"] is None or a["backlogs"] > drive.max_backlogs):
        fail("backlog", "Backlog Policy", f"≤ {drive.max_backlogs}",
             f"{a['backlogs'] if a['backlogs'] is not None else 'unknown'}", False)
    if drive.min_readiness is not None and (a["readiness"] is None or a["readiness"] < drive.min_readiness):
        fail("readiness", "Placement Readiness", f"≥ {drive.min_readiness:g}",
             f"{a['readiness'] if a['readiness'] is not None else 'not analyzed'}", True)
    if drive.min_coding is not None:
        v = a["skills"].get("CODING")
        if v is None or v < drive.min_coding:
            fail("coding", "Coding Score", f"≥ {drive.min_coding:g}",
                 f"{v if v is not None else 'not assessed'}", True)
    if drive.min_aptitude is not None:
        v = a["skills"].get("APTITUDE")
        if v is None or v < drive.min_aptitude:
            fail("aptitude", "Aptitude Score", f"≥ {drive.min_aptitude:g}",
                 f"{v if v is not None else 'not assessed'}", True)
    if drive.min_communication is not None:
        v = a["skills"].get("COMMUNICATION")
        if v is None or v < drive.min_communication:
            fail("communication", "Communication Score", f"≥ {drive.min_communication:g}",
                 f"{v if v is not None else 'not assessed'}", True)
    if drive.project_required and a["verified_projects"] < 1:
        fail("project", "Verified Project", "at least 1", "0", True)
    if drive.internship_required and a["verified_internships"] < 1:
        fail("internship", "Verified Internship", "at least 1", "0", True)
    if drive.target_branches and st.branch not in drive.target_branches:
        fail("branch", "Target Branch", ", ".join(drive.target_branches), st.branch, False)
    if drive.eligible_semesters and st.semester not in drive.eligible_semesters:
        fail("semester", "Eligible Semester", ", ".join(str(x) for x in drive.eligible_semesters),
             str(st.semester), False)
    return blockers


# ---------------------------------------------------------------- match score
def _skill_alignment(scores: list[float]) -> float | None:
    return mean(scores) if scores else None


def _match_components(drive: PlacementDrive, inp: dict) -> dict[str, float | None]:
    """Per-component 0..1 values (None = not applicable for this drive)."""
    skills = inp["skills"]
    out: dict[str, float | None] = {}

    req = drive.required_skills or []
    if req:
        out["required_skills"] = min(1.0, _skill_alignment([min(1.0, skills.get(c, 0) / 100.0) for c in req]))
    else:
        out["required_skills"] = None

    pref = drive.preferred_skills or []
    if pref:
        out["preferred_skills"] = min(1.0, _skill_alignment([min(1.0, skills.get(c, 0) / 100.0) for c in pref]))
    else:
        out["preferred_skills"] = None

    if drive.preferred_career_code:
        out["career"] = (inp["career"].get(drive.preferred_career_code, 0) / 100.0) or None
    else:
        out["career"] = (max(inp["career"].values(), default=0) / 100.0) or None

    out["readiness"] = (inp["readiness"] or 0) / 100.0 if inp["readiness"] is not None else None

    ca: list[float] = []
    if drive.min_coding:
        v = skills.get("CODING")
        ca.append(min(1.0, (v or 0) / drive.min_coding) if v is not None else 0.0)
    if drive.min_aptitude:
        v = skills.get("APTITUDE")
        ca.append(min(1.0, (v or 0) / drive.min_aptitude) if v is not None else 0.0)
    out["coding_aptitude"] = mean(ca) if ca else None

    proj = min(inp["verified_projects"], 3) / 3.0 * 0.6
    intern = 0.4 if inp["verified_internships"] >= 1 else 0.0
    out["project_internship"] = proj + intern
    return out


def _score(components: dict[str, float | None], weights: dict[str, float]) -> float | None:
    num = 0.0
    den = 0.0
    for k, w in weights.items():
        v = components.get(k)
        if v is None:
            continue
        num += w * v
        den += w
    if den == 0:
        return None
    return round(num / den * 100, 1)


def _explanation(drive: PlacementDrive, inp: dict, blockers: list[dict],
                 components: dict[str, float | None]) -> dict:
    matched: list[str] = []
    skills = inp["skills"]

    def _chk(ok: bool | None, text: str | None) -> None:
        if ok is True and text:
            matched.append(text)

    if inp["cgpa"] is not None and drive.min_cgpa is not None and inp["cgpa"] >= drive.min_cgpa:
        _chk(True, f"CGPA {inp['cgpa']:g} ≥ {drive.min_cgpa:g}")
    if inp["tenth"] is not None and drive.min_tenth is not None and inp["tenth"] >= drive.min_tenth:
        _chk(True, f"10th {inp['tenth']:g} ≥ {drive.min_tenth:g}")
    if inp["twelfth"] is not None and drive.min_twelfth is not None and inp["twelfth"] >= drive.min_twelfth:
        _chk(True, f"12th {inp['twelfth']:g} ≥ {drive.min_twelfth:g}")
    if inp["backlogs"] is not None and drive.max_backlogs is not None and inp["backlogs"] <= drive.max_backlogs:
        _chk(True, f"Backlogs {inp['backlogs']} ≤ {drive.max_backlogs}")
    if inp["readiness"] is not None and drive.min_readiness is not None and inp["readiness"] >= drive.min_readiness:
        _chk(True, f"Readiness {inp['readiness']:g} ≥ {drive.min_readiness:g}")
    if skills.get("CODING") is not None and drive.min_coding is not None and skills["CODING"] >= drive.min_coding:
        _chk(True, f"Coding {skills['CODING']:g} ≥ {drive.min_coding:g}")
    if skills.get("APTITUDE") is not None and drive.min_aptitude is not None and skills["APTITUDE"] >= drive.min_aptitude:
        _chk(True, f"Aptitude {skills['APTITUDE']:g} ≥ {drive.min_aptitude:g}")
    if skills.get("COMMUNICATION") is not None and drive.min_communication is not None \
            and skills["COMMUNICATION"] >= drive.min_communication:
        _chk(True, f"Communication {skills['COMMUNICATION']:g} ≥ {drive.min_communication:g}")
    if drive.project_required and inp["verified_projects"] >= 1:
        _chk(True, f"{inp['verified_projects']} verified project(s)")
    if drive.internship_required and inp["verified_internships"] >= 1:
        _chk(True, f"{inp['verified_internships']} verified internship(s)")

    pref_matches = [SKILL_LABELS.get(c, c) for c in (drive.preferred_skills or [])
                    if inp["skills"].get(c, 0) >= 75]
    req_matches = [SKILL_LABELS.get(c, c) for c in (drive.required_skills or [])
                   if inp["skills"].get(c, 0) >= 70]

    opportunities: list[str] = []
    for b in blockers:
        if b["actionable"]:
            opportunities.append(b["label"])
    for c in (drive.preferred_skills or []):
        v = inp["skills"].get(c)
        if v is not None and v < 60:
            opportunities.append(f"{SKILL_LABELS.get(c, c)} ({v:g} → 60+)")
    # dedupe, preserve order
    seen = set()
    opportunities = [o for o in opportunities if not (o in seen or seen.add(o))]

    lines: list[str] = []
    if not blockers:
        lines.append("You satisfy all mandatory eligibility requirements for this drive.")
    else:
        lines.append(f"{len(blockers)} mandatory requirement(s) are currently unmet: "
                     + "; ".join(f"{b['label']} ({b['actual']} vs {b['required']})" for b in blockers))
    if req_matches:
        lines.append(f"Your verified skills strongly align with the {drive.role} role: "
                     + ", ".join(req_matches) + ".")
    if pref_matches:
        lines.append(f"Preferred strengths also match: {', '.join(pref_matches)}.")
    if opportunities:
        lines.append("Largest improvement opportunities: " + ", ".join(opportunities[:3]) + ".")
    return {
        "matched_requirements": matched,
        "required_matches": req_matches,
        "preferred_matches": pref_matches,
        "improvement_opportunities": opportunities[:5],
        "explanation": lines,
    }


# ---------------------------------------------------------------- core
def evaluate_one(drive: PlacementDrive, st: Student, inp: dict, weights: dict[str, float]) -> dict | None:
    """Evaluate one (student, drive) pair. None when the student isn't analyzed."""
    if inp["readiness"] is None:
        return None
    blockers = _check_mandatory(drive, inp, st)
    eligible = not blockers
    components = _match_components(drive, inp)
    score = _score(components, weights) if eligible else _score(components, weights)
    # score is always computed (it informs "almost eligible"), but the UI must
    # never present it as overriding eligibility.
    exp = _explanation(drive, inp, blockers, components)
    actionable_blockers = [b for b in blockers if b["actionable"]]
    almost = (not eligible) and 1 <= len(actionable_blockers) <= 2 \
        and not [b for b in blockers if not b["actionable"]]
    return {
        "eligible": eligible,
        "almost_eligible": almost,
        "match_score": score if score is not None else 0.0,
        "mandatory_blockers": blockers,
        "actionable_blockers": actionable_blockers,
        "components": {k: (None if v is None else round(v * 100, 1)) for k, v in components.items()},
        "component_labels": COMPONENT_LABELS,
        **exp,
    }


def _drive_public(db: Session, drive: PlacementDrive, extra: dict | None = None) -> dict:
    d = {
        "drive_id": drive.id,
        "company": {"id": drive.company_id, "name": drive.company.name,
                    "industry": drive.company.industry, "location": drive.location or drive.company.location},
        "title": drive.title, "role": drive.role,
        "job_description": drive.job_description,
        "location": drive.location or drive.company.location,
        "ctc": drive.ctc, "employment_type": drive.employment_type,
        "drive_date": drive.drive_date, "deadline": drive.deadline,
        "open_positions": drive.open_positions,
        "status": drive.status,
        "criteria": {
            "min_cgpa": drive.min_cgpa, "min_tenth": drive.min_tenth,
            "min_twelfth": drive.min_twelfth, "max_backlogs": drive.max_backlogs,
            "min_readiness": drive.min_readiness, "min_coding": drive.min_coding,
            "min_aptitude": drive.min_aptitude, "min_communication": drive.min_communication,
            "project_required": drive.project_required, "internship_required": drive.internship_required,
            "target_branches": drive.target_branches, "eligible_semesters": drive.eligible_semesters,
            "required_skills": drive.required_skills, "preferred_skills": drive.preferred_skills,
            "preferred_career_code": drive.preferred_career_code,
        },
    }
    if extra:
        d.update(extra)
    return d


def matches_for_student(db: Session, st: Student, statuses: tuple = ("OPEN",)) -> list[dict]:
    """Student -> ranked company opportunities (active companies' drives)."""
    from app.models import Company
    weights = get_settings().company_match_weights
    drives = db.execute(select(PlacementDrive).where(
        PlacementDrive.status.in_(statuses),
        PlacementDrive.company_id.in_(
            select(Company.id).where(Company.status == "ACTIVE")))).scalars().all()
    if st.available_for_placement is False:
        return []
    inp = _load_inputs(db).get(st.id)
    if inp is None:
        return []
    out = []
    for drive in drives:
        r = evaluate_one(drive, st, inp, weights)
        if r is None:
            continue
        out.append(_drive_public(db, drive, r))
    out.sort(key=lambda x: (0 if x["eligible"] else 1, -x["match_score"]))
    return out


def matches_for_drive(db: Session, drive: PlacementDrive,
                      student_ids: set[int] | None = None) -> list[dict]:
    """Drive -> ranked candidates (all analyzed students in the pool)."""
    s = get_settings()
    weights = s.company_match_weights
    students = {sid: db.get(Student, sid) for sid in (student_ids or [])}
    inputs = _load_inputs(db)
    out = []
    for sid, st in students.items():
        if st is None or not st.is_active:
            continue
        r = evaluate_one(drive, st, inputs.get(sid, {}), weights)
        if r is None:
            continue
        out.append({
            "student_id": sid,
            "usn": st.usn, "name": st.user.display_name if st.user else st.usn,
            "branch": st.branch, "semester": st.semester,
            "readiness": inputs[sid]["readiness"],
            "category": inputs[sid]["category"],
            "cgpa": inputs[sid]["cgpa"],
            "coding": inputs[sid]["skills"].get("CODING"),
            "aptitude": inputs[sid]["skills"].get("APTITUDE"),
            "communication": inputs[sid]["skills"].get("COMMUNICATION"),
            "career_best": max(inputs[sid]["career"].items(), key=lambda kv: kv[1], default=(None, 0))[0],
            "skills": {c: inputs[sid]["skills"][c] for c in (drive.required_skills or []) + (drive.preferred_skills or [])
                       if c in inputs[sid]["skills"]},
            **r,
        })
    out.sort(key=lambda x: (0 if x["eligible"] else 1, -x["match_score"]))
    return out
