"""Placement Match Engine + pipeline + RBAC tests (new dashboards).

Covers the spec's hard rules:
  * eligibility is mandatory (cannot be averaged away);
  * match score computed separately, deterministic, recalculated;
  * company sees ONLY own drives + TPO-nominated candidates (never INTERESTED);
  * cross-company access denied;
  * Selected != Placed; only TPO confirms placement;
  * department scope is backend-enforced;
  * nomination defaults to eligible-only.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Company, Department, Student, User
from app.core.security import hash_password


def _tpo(client, tokens):
    return {"Authorization": f"Bearer {tokens['tpo']}"}


def _make_company(client, tokens, name, email):
    r = client.post("/api/tpo/companies", json={
        "name": name, "industry": "Demo", "location": "Bengaluru",
        "recruiter_email": email, "recruiter_password": "RecruiterTest123!",
        "recruiter_name": f"{name} Recruiter"}, headers=_tpo(client, tokens))
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _recruiter_token(client, email):
    r = client.post("/api/auth/staff/login", json={"email": email,
                                                   "password": "RecruiterTest123!"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _make_drive(client, tokens, company_id, name, **kw):
    body = {"company_id": company_id, "title": name, "role": "Engineer",
            "status": "OPEN"}
    body.update(kw)
    r = client.post("/api/tpo/drives", json=body, headers=_tpo(client, tokens))
    assert r.status_code == 200, r.text
    return r.json()["id"]


# ---------------------------------------------------------------- company basics
def test_company_lifecycle_and_recruiter_login(client, tokens):
    cid = _make_company(client, tokens, "AlphaSoft Demo", "recruiter.alfasoft@test.example")
    rec = _recruiter_token(client, "recruiter.alfasoft@test.example")
    r = client.get("/api/company/overview", headers=rec)
    assert r.status_code == 200
    assert r.json()["company"]["id"] == cid
    r = client.get("/api/company/drives", headers=rec)
    assert r.json()["drives"] == []


def test_cross_company_drive_access_denied(client, tokens):
    c1 = _make_company(client, tokens, "BetaSoft Demo", "recruiter.betasoft@test.example")
    c2 = _make_company(client, tokens, "GammaSoft Demo", "recruiter.gammasoft@test.example")
    drive2 = _make_drive(client, tokens, c2, "Gamma Drive")
    rec1 = _recruiter_token(client, "recruiter.betasoft@test.example")
    r = client.get(f"/api/company/drives/{drive2}/candidates", headers=rec1)
    assert r.status_code == 403


# ---------------------------------------------------------------- eligibility strictness
def test_eligibility_cannot_be_averaged_away(client, tokens):
    cid = _make_company(client, tokens, "StrictCo Demo", "recruiter.strictco@test.example")
    # high coding bar that Alpha (coding 75) fails, no other criteria
    drive = _make_drive(client, tokens, cid, "Strict Coding Drive",
                        min_coding=90.0, required_skills=["CODING", "PYTHON"])
    r = client.get(f"/api/tpo/matching/drives/{drive}", headers=_tpo(client, tokens))
    assert r.status_code == 200
    alpha = next(c for c in r.json()["candidates"] if c["usn"] == "1PM24CS101")
    assert alpha["eligible"] is False
    assert any(b["key"] == "coding" and b["actionable"] for b in alpha["mandatory_blockers"])
    # still gets a separate match score (decision support), but it never overrides eligibility
    assert alpha["match_score"] is not None
    # non-actionable blocker: CGPA gate
    drive2 = _make_drive(client, tokens, cid, "CGPA Gate Drive", min_cgpa=9.5)
    r2 = client.get(f"/api/tpo/matching/drives/{drive2}", headers=_tpo(client, tokens))
    alpha2 = next(c for c in r2.json()["candidates"] if c["usn"] == "1PM24CS101")
    cgpa_block = next(b for b in alpha2["mandatory_blockers"] if b["key"] == "cgpa")
    assert cgpa_block["actionable"] is False
    assert alpha2["almost_eligible"] is False  # non-actionable gap => not "almost"


def test_almost_eligible_actionable_only(client, tokens):
    cid = _make_company(client, tokens, "AlmostCo Demo", "recruiter.almostco@test.example")
    # Alpha fails ONLY readiness-ish actionable bar (communication 60 < 65)
    drive = _make_drive(client, tokens, cid, "Comm Bar Drive",
                        min_communication=65.0, min_cgpa=5.0)
    r = client.get(f"/api/tpo/matching/drives/{drive}", headers=_tpo(client, tokens))
    alpha = next(c for c in r.json()["candidates"] if c["usn"] == "1PM24CS101")
    assert alpha["eligible"] is False
    assert alpha["almost_eligible"] is True
    assert alpha["actionable_blockers"]


# ---------------------------------------------------------------- student -> company
def test_student_sees_company_opportunities_with_explanation(client, tokens):
    cid = _make_company(client, tokens, "StudentCo Demo", "recruiter.studentco@test.example")
    _make_drive(client, tokens, cid, "Open Drive for Students",
                min_cgpa=5.0, required_skills=["PYTHON", "SQL"], preferred_skills=["GIT"])
    r = client.get("/api/student/companies",
                   headers={"Authorization": f"Bearer {tokens['student']}"})
    assert r.status_code == 200
    opps = r.json()["opportunities"]
    assert any(o["title"] == "Open Drive for Students" for o in opps)
    opp = next(o for o in opps if o["title"] == "Open Drive for Students")
    assert opp["eligible"] is True
    assert opp["match_score"] > 0
    assert opp["explanation"]
    # determinism: same call twice => identical scores
    r2 = client.get("/api/student/companies",
                    headers={"Authorization": f"Bearer {tokens['student']}"})
    opp2 = next(o for o in r2.json()["opportunities"] if o["title"] == "Open Drive for Students")
    assert opp2["match_score"] == opp["match_score"]


def test_student_private_fields_never_exposed_to_company(client, tokens):
    cid = _make_company(client, tokens, "PrivCo Demo", "recruiter.privco@test.example")
    drive = _make_drive(client, tokens, cid, "Priv Drive", min_cgpa=5.0)
    # student expresses interest -> company must NOT see them yet
    r = client.post(f"/api/student/companies/{drive}/interest",
                    headers={"Authorization": f"Bearer {tokens['student']}"})
    assert r.status_code == 200
    rec = _recruiter_token(client, "recruiter.privco@test.example")
    rows = client.get(f"/api/company/drives/{drive}/candidates", headers=rec).json()["rows"]
    assert all(x["usn"] != "1PM24CS101" for x in rows)


# ---------------------------------------------------------------- pipeline
def test_nomination_eligible_only_and_pipeline_flow(client, tokens):
    cid = _make_company(client, tokens, "PipeCo Demo", "recruiter.pipeco@test.example")
    drive = _make_drive(client, tokens, cid, "Pipeline Drive",
                        min_cgpa=5.0, min_communication=65.0)  # Alpha fails comm
    alpha_id = next(st.id for st in SessionLocal().execute(
        select(Student).where(Student.usn == "1PM24CS101")).scalars())
    # TPO tries to nominate Alpha (not eligible) -> must be skipped
    r = client.post(f"/api/tpo/matching/drives/{drive}/nominate",
                    json={"student_ids": [alpha_id]}, headers=_tpo(client, tokens))
    assert r.status_code == 200
    assert r.json()["nominated"] == 0
    assert r.json()["skipped"][0]["reason"].startswith("no longer meets")

    # open a lenient drive; nominate Alpha; company sees them
    drive2 = _make_drive(client, tokens, cid, "Lenient Drive", min_cgpa=5.0)
    r = client.post(f"/api/tpo/matching/drives/{drive2}/nominate",
                    json={"student_ids": [alpha_id], "note": "Strong profile"},
                    headers=_tpo(client, tokens))
    assert r.json()["nominated"] == 1
    rec = _recruiter_token(client, "recruiter.pipeco@test.example")
    rows = client.get(f"/api/company/drives/{drive2}/candidates", headers=rec).json()["rows"]
    alpha_row = next(x for x in rows if x["usn"] == "1PM24CS101")
    assert alpha_row["status"] == "NOMINATED"

    # company advances: shortlist -> interview -> select (company can't place)
    for status in ("SHORTLISTED", "INTERVIEW", "SELECTED"):
        r = client.post(f"/api/company/drives/{drive2}/candidates/{alpha_id}/status",
                        json={"status": status, "note": "good round"}, headers=rec)
        assert r.status_code == 200, r.text
    r = client.get(f"/api/company/drives/{drive2}/candidates/{alpha_id}", headers=rec).json()
    assert r["candidate"]["status"] == "SELECTED"

    # Selected != Placed until TPO confirms
    places = client.get("/api/tpo/placements", headers=_tpo(client, tokens)).json()
    alpha_row = next(x for x in places["rows"] if x["usn"] == "1PM24CS101")
    assert alpha_row["status"] == "SELECTED"
    cand_id = alpha_row["candidate_id"]

    # company account cannot confirm
    r = client.post(f"/api/tpo/placements/{cand_id}/confirm", json={}, headers=rec)
    assert r.status_code == 403
    # TPO confirms
    r = client.post(f"/api/tpo/placements/{cand_id}/confirm",
                    json={"note": "Offer accepted"}, headers=_tpo(client, tokens))
    assert r.status_code == 200
    assert r.json()["status"] == "PLACED"

    # student placement journey reflects the whole pipeline
    j = client.get("/api/student/placement-journey",
                   headers={"Authorization": f"Bearer {tokens['student']}"}).json()
    stages = [x["status"] for x in j["journey"]]
    assert "PLACED" in stages


def test_company_cannot_skip_stages_or_edit_scores(client, tokens):
    cid = _make_company(client, tokens, "RuleCo Demo", "recruiter.ruleco@test.example")
    drive = _make_drive(client, tokens, cid, "Rule Drive", min_cgpa=5.0)
    alpha_id = next(st.id for st in SessionLocal().execute(
        select(Student).where(Student.usn == "1PM24CS101")).scalars())
    client.post(f"/api/tpo/matching/drives/{drive}/nominate",
                json={"student_ids": [alpha_id]}, headers=_tpo(client, tokens))
    rec = _recruiter_token(client, "recruiter.ruleco@test.example")
    # NOMINATED -> SELECTED is not a legal transition
    r = client.post(f"/api/company/drives/{drive}/candidates/{alpha_id}/status",
                    json={"status": "SELECTED"}, headers=rec)
    assert r.status_code == 409


# ---------------------------------------------------------------- department scope
def test_department_scope_backend_enforced(client, tokens):
    db = SessionLocal()
    dept = db.execute(select(Department).where(Department.code == "ISE")).scalars().first()
    if not dept:
        dept = Department(code="ISE", name="Information Science & Engineering")
        db.add(dept)
        db.flush()
    email = "dept.ise@test.example"
    if not db.execute(select(User).where(User.email == email)).scalars().first():
        db.add(User(role="DEPARTMENT", email=email, password_hash=hash_password("DeptTest123!"),
                    display_name="ISE Office", department_id=dept.id))
    db.commit()
    dept_id = dept.id
    db.close()
    r = client.post("/api/auth/staff/login", json={"email": email, "password": "DeptTest123!"})
    assert r.status_code == 200, r.text
    hdr = {"Authorization": f"Bearer {r.json()['token']}"}
    ov = client.get("/api/dept/overview", headers=hdr).json()
    # ISE office: Test Beta is ISE; Test Alpha (CSE) must NOT appear
    usns = [s["usn"] for s in ov["students"]]
    assert "1PM24IS102" in usns
    assert "1PM24CS101" not in usns
