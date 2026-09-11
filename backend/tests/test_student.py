"""Student-facing flows: readiness, passport, career, optimizer, what-if, roadmap."""


def _readiness(client, tokens, usn_token="student"):
    r = client.get("/api/student/readiness", headers={"Authorization": f"Bearer {tokens[usn_token]}"})
    assert r.status_code == 200
    return r.json()


def test_readiness_shape_and_terms(client, tokens):
    d = _readiness(client, tokens)
    assert d["status"] == "ok"
    p = d["prediction"]
    assert 0 <= p["score"] <= 100
    assert p["category"] in ("READY", "NEAR_READY", "NEEDS_TRAINING")
    assert p["category_label"] in ("Ready", "Near-Ready", "Needs Training")
    assert p["model_version"]
    assert isinstance(p["profile_trust"], (int, float))
    assert 0 <= p["profile_trust"] <= 100
    assert "feature_snapshot" in p
    # XAI present with friendly labels and no raw feature names leaked
    assert len(d["xai"]["positive"]) >= 1 or len(d["xai"]["limiting"]) >= 1
    for c in d["xai"]["positive"] + d["xai"]["limiting"]:
        assert c["label"] and "score" not in c["label"]
    # summary sentence is constructive and present
    assert d["summary_sentence"]


def test_trust_and_completeness_present(client, tokens):
    d = _readiness(client, tokens)
    assert 0 <= d["trust"]["score"] <= 100
    assert d["trust"]["band"]
    assert 0 <= d["completeness"]["score"] <= 100
    assert d["eligibility"]["eligible"] is True


def test_career_matches_two_tracks(client, tokens):
    r = client.get("/api/student/career", headers={"Authorization": f"Bearer {tokens['student']}"})
    assert r.status_code == 200
    d = r.json()
    codes = {m["career_code"] for m in d["matches"]}
    assert {"FULL_STACK", "DATA_ANALYST"} <= codes
    # distinct benchmarks -> distinct scores generally; ensure detail has comparisons
    assert d["detail"]["comparisons"]


def test_set_target_career(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['weak_student']}"}
    r = client.post("/api/student/career/target", json={"career_code": "DATA_ANALYST"}, headers=hdr)
    assert r.status_code == 200
    r = client.post("/api/student/career/target", json={"career_code": "NOT_A_TRACK"}, headers=hdr)
    assert r.status_code == 400


def test_optimizer_minimum_change(client, tokens):
    r = client.get("/api/student/optimizer", headers={"Authorization": f"Bearer {tokens['weak_student']}"})
    assert r.status_code == 200
    d = r.json()
    assert d["baseline_readiness"] is not None
    assert "model" in d["disclaimer"].lower()
    # no fixed/historical features may be recommended
    for a in d["actions"]:
        assert a["feature"] not in ("cgpa", "tenth_percentage", "twelfth_percentage",
                                    "backlog_history_count")
        assert a["target_value"] > a["current_value"]
        assert a["estimated_weeks"] >= 1
        assert a["reason"]


def test_optimizer_ready_student_short_circuits(client, tokens):
    # Test Alpha is strong; if already Ready, optimizer reports reached
    r = client.get("/api/student/optimizer", headers={"Authorization": f"Bearer {tokens['student']}"})
    d = r.json()
    if d["baseline_readiness"] >= 80:
        assert d["target_reached"] is True


def test_what_if_simulation(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['weak_student']}"}
    r = client.post("/api/student/what-if/simulate",
                    json={"changes": [{"feature": "sql_score", "value": 65}]}, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["projected_readiness"] >= d["baseline_readiness"]
    assert "hypothetical" in d["disclaimer"].lower()


def test_what_if_rejects_fixed_feature(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['weak_student']}"}
    r = client.post("/api/student/what-if/simulate",
                    json={"changes": [{"feature": "cgpa", "value": 9.5}]}, headers=hdr)
    assert r.status_code == 400


def test_what_if_rejects_out_of_range(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['weak_student']}"}
    r = client.post("/api/student/what-if/simulate",
                    json={"changes": [{"feature": "sql_score", "value": 150}]}, headers=hdr)
    assert r.status_code == 422  # pydantic range guard


def test_roadmap_generated_and_persisted(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['weak_student']}"}
    r = client.post("/api/student/roadmap/generate", json={"target_type": "GENERAL_READINESS"}, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    rm = d["roadmap"]
    assert rm and len(rm["items"]) >= 1
    for it in rm["items"]:
        assert it["tasks"] and it["milestone"]
        assert it["priority"] in ("Critical", "High", "Medium")
    r2 = client.get("/api/student/roadmap", headers=hdr)
    assert r2.status_code == 200
    assert r2.json()["roadmap"]["id"] == rm["id"]


def test_roadmap_item_status_update(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['weak_student']}"}
    r = client.get("/api/student/roadmap", headers=hdr)
    rm = r.json()["roadmap"]
    if not rm:
        r = client.post("/api/student/roadmap/generate", json={"target_type": "GENERAL_READINESS"}, headers=hdr)
        rm = r.json()["roadmap"]
    item_id = rm["items"][0]["id"]
    r = client.patch(f"/api/student/roadmap/items/{item_id}", json={"status": "IN_PROGRESS"}, headers=hdr)
    assert r.status_code == 200
    r = client.patch(f"/api/student/roadmap/items/{item_id}", json={"status": "BOGUS"}, headers=hdr)
    assert r.status_code == 422


def test_student_skill_catalog(client, tokens):
    r = client.get("/api/student/skills", headers={"Authorization": f"Bearer {tokens['student']}"})
    assert r.status_code == 200
    assert len(r.json()["skills"]) >= 15
