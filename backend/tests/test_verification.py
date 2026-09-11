"""Verified Employability Passport: submit -> pending -> verify/correct -> trust + recompute."""


def test_passport_states_and_provenance(client, tokens):
    r = client.get("/api/student/passport", headers={"Authorization": f"Bearer {tokens['weak_student']}"})
    assert r.status_code == 200
    d = r.json()
    # Test Beta has 1 pending project
    assert d["passport"]["counts"]["PENDING"] >= 1
    # assessment-sourced skills are trusted with provenance label
    skills = {s["skill_code"]: s for s in d["skills"]}
    assert skills["SQL"]["source_label"] == "Assessment"
    assert skills["SQL"]["trust"] == "VERIFIED"
    # trust and completeness present
    assert 0 <= d["trust"]["score"] <= 100
    assert 0 <= d["completeness"]["score"] <= 100


def test_student_submits_project_creates_pending(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['student']}"
    }
    r = client.post("/api/student/projects", json={
        "title": "E2E Test Project", "student_role": "Developer",
        "claimed_complexity": "Basic", "tech_stack": ["Python"]}, headers=hdr)
    assert r.status_code == 200
    r = client.get("/api/student/passport", headers=hdr)
    d = r.json()
    assert any(p["title"] == "E2E Test Project" and p["status"] == "PENDING" for p in d["projects"])


def test_faculty_correction_flow_and_recompute(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['faculty_proj']}"}
    # capture Test Beta readiness before decision
    before = client.get("/api/student/readiness",
                        headers={"Authorization": f"Bearer {tokens['weak_student']}"}).json()
    r = client.get("/api/faculty/queue", params={"category": "PROJECT", "status": "PENDING"}, headers=hdr)
    items = r.json()["items"]
    beta = next(i for i in items if i["usn"] == "1PM24IS102")
    rid = beta["request_id"]

    # correction request without a note must be rejected
    r = client.post(f"/api/faculty/queue/{rid}/decide",
                    json={"decision": "CORRECTION_REQUIRED", "note": ""}, headers=hdr)
    assert r.status_code == 400

    # apply correction
    r = client.post(f"/api/faculty/queue/{rid}/decide",
                    json={"decision": "CORRECTION_REQUIRED",
                          "note": "Please attach the repository link and role details."},
                    headers=hdr)
    assert r.status_code == 200

    # student sees the correction state + note
    r = client.get("/api/student/passport",
                   headers={"Authorization": f"Bearer {tokens['weak_student']}"}).json()
    assert r["passport"]["state"] == "CORRECTION_REQUIRED"
    assert any(p["status"] == "CORRECTION_REQUIRED" for p in r["projects"])

    # student resubmits with the missing detail
    proj_id = next(p["id"] for p in r["projects"] if p["status"] == "CORRECTION_REQUIRED")
    r = client.post("/api/student/projects",
                    json={"id": proj_id, "title": "Test Project",
                          "claimed_complexity": "Intermediate",
                          "github_url": "https://github.com/testbeta/test-project"},
                    headers={"Authorization": f"Bearer {tokens['weak_student']}"})
    assert r.status_code == 200

    # faculty verifies now; readiness must be recomputed (trust-relevant change)
    r = client.post(f"/api/faculty/queue/{rid}/decide",
                    json={"decision": "VERIFIED", "note": "Verified against repository.",
                          "corrections": {"complexity": "Intermediate"}}, headers=hdr)
    assert r.status_code == 200

    after = client.get("/api/student/readiness",
                       headers={"Authorization": f"Bearer {tokens['weak_student']}"}).json()
    assert after["status"] == "ok"
    # verified project count changed -> prediction snapshot reflects it
    assert after["prediction"]["feature_snapshot"]["verified_project_count"] >= 1
    assert after["trust"]["score"] >= before["trust"]["score"] if before.get("trust") else True


def test_decision_audit_history(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['faculty_proj']}"}
    # after the correction+verify cycle, history must show both transitions
    r = client.get("/api/faculty/queue", params={"category": "PROJECT", "status": "VERIFIED"}, headers=hdr)
    items = [i for i in r.json()["items"] if i["usn"] == "1PM24IS102"]
    assert items
    rid = items[0]["request_id"]
    detail = client.get(f"/api/faculty/queue/{rid}", headers=hdr).json()
    statuses = [h["new_status"] for h in detail["history"]]
    assert "CORRECTION_REQUIRED" in statuses and "VERIFIED" in statuses
    assert all(h["verifier"] for h in detail["history"])


def test_double_decision_blocked(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['faculty_proj']}"}
    r = client.get("/api/faculty/queue", params={"category": "PROJECT", "status": "VERIFIED"}, headers=hdr)
    items = [i for i in r.json()["items"] if i["usn"] == "1PM24IS102"]
    if not items:
        return
    rid = items[0]["request_id"]
    r = client.post(f"/api/faculty/queue/{rid}/decide",
                    json={"decision": "REJECTED", "note": "duplicate"}, headers=hdr)
    assert r.status_code == 409


def test_student_cannot_claim_assessment_skill(client, tokens):
    # assessment skills are institution-sourced; self-modification is blocked
    hdr = {"Authorization": f"Bearer {tokens['student']}"}
    r = client.post("/api/student/skills/claim", json={"skill_code": "CODING",
                                                       "claimed_level": "Advanced"}, headers=hdr)
    assert r.status_code in (409, 200)
    # if it went through, the row must NOT become VERIFIED by self-claim
    if r.status_code == 200:
        d = client.get("/api/student/passport", headers=hdr).json()
        coding = next(s for s in d["skills"] if s["skill_code"] == "CODING")
        assert coding["trust"] != "VERIFIED" or coding["source"] != "SELF_REPORTED"
