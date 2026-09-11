"""TPO analytics: overview, heatmap, drilldown, interventions, simulation, import."""


def test_overview_computed(client, tokens):
    r = client.get("/api/tpo/overview", headers={"Authorization": f"Bearer {tokens['tpo']}"})
    assert r.status_code == 200
    d = r.json()
    rd = d["readiness"]
    # the small test seed has analyzed students; percentages must be internally consistent
    assert rd["ready"] + rd["near_ready"] + rd["needs_training"] == d["population"]["analyzed_students"]
    assert rd["ready_percentage"] is None or 0 <= rd["ready_percentage"] <= 100
    assert d["branch_metrics"]
    for b in d["branch_metrics"]:
        assert 0 <= b["ready_percentage"] <= 100


def test_overview_branch_filter(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['tpo']}"}
    full = client.get("/api/tpo/overview", headers=hdr).json()
    filt = client.get("/api/tpo/overview", params={"branch": "CSE"}, headers=hdr).json()
    assert filt["population"]["analyzed_students"] <= full["population"]["analyzed_students"]
    assert all(b["branch"] == "CSE" for b in filt["branch_metrics"])


def test_student_list_filters(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['tpo']}"}
    r = client.get("/api/tpo/students", params={"max_score": 59}, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["total"] >= 1
    assert all(s["readiness"] <= 59 for s in d["items"])


def test_skill_heatmap_and_drilldown(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['tpo']}"}
    r = client.get("/api/tpo/skills", headers=hdr)
    d = r.json()
    assert d["deficits"]
    # heatmap cells carry benchmark-below percentage + counts
    if d["heatmap"]:
        for cell in d["heatmap"]:
            assert 0 <= cell["below_benchmark_percentage"] <= 100
            assert cell["evaluated_count"] >= cell["below_benchmark_count"]
    top = d["deficits"][0]["skill"]
    r = client.get(f"/api/tpo/skills/{top}/drilldown", headers=hdr)
    assert r.status_code == 200
    dd = r.json()
    assert dd["count"] >= 1
    assert all(s["score"] <= dd["benchmark"] for s in dd["students"])


def test_vulnerable_cohorts(client, tokens):
    r = client.get("/api/tpo/cohorts/vulnerable", headers={"Authorization": f"Bearer {tokens['tpo']}"})
    assert r.status_code == 200
    assert isinstance(r.json()["cohorts"], list)


def test_interventions_ranked_and_disclaimer(client, tokens):
    r = client.get("/api/tpo/interventions", headers={"Authorization": f"Bearer {tokens['tpo']}"})
    assert r.status_code == 200
    d = r.json()
    ivs = d["interventions"]
    assert ivs
    # ranked by score (descending)
    scores = [i["score"] for i in ivs]
    assert scores == sorted(scores, reverse=True)
    for i in ivs:
        assert 0 <= i["affected_share"] <= 1


def test_intervention_simulation_projection(client, tokens):
    r = client.get("/api/tpo/interventions", headers={"Authorization": f"Bearer {tokens['tpo']}"})
    ivs = r.json()["interventions"]
    assert ivs
    code = ivs[0]["code"]
    r = client.post("/api/tpo/interventions/simulate",
                    json={"intervention_code": code, "improvement": 20},
                    headers={"Authorization": f"Bearer {tokens['tpo']}"})
    assert r.status_code == 200
    d = r.json()
    assert d["status"] in ("ok", "empty_cohort")
    if d["status"] == "ok":
        sim = d["simulation"]
        assert sim["cohort_size"] >= 1
        assert "model-based projection" in d["disclaimer"].lower()
        # projected distribution must conserve cohort size
        proj = sim["projected"]
        assert proj["READY"] + proj["NEAR_READY"] + proj["NEEDS_TRAINING"] == sim["cohort_size"]


def test_import_validate_confirm(client, tokens):
    hdr = {"Authorization": f"Bearer {tokens['tpo']}"}
    import io
    import pandas as pd
    # the test DB has different USNs than the 600-student demo; craft a valid batch.
    # Unknown USNs are now CREATED (upsert); skill columns create verified rows.
    batch = pd.DataFrame([
        {"usn": "1PM24CS101", "branch": "CSE", "semester": 4, "cgpa": 8.0,
         "tenth_percentage": 81.0, "twelfth_percentage": 79.0, "backlog_history_count": 0},
        {"usn": "1PM24IS102", "branch": "ISE", "semester": 4, "cgpa": 6.0,
         "tenth_percentage": 70.0, "twelfth_percentage": 68.0, "backlog_history_count": 1},
        {"usn": "1PM24CS999", "name": "New Student", "branch": "CSE", "semester": 4,
         "cgpa": 9.9, "tenth_percentage": 99.0, "twelfth_percentage": 99.0,
         "backlog_history_count": 0, "coding": 80, "aptitude": 75, "communication": 70},  # new student
        {"usn": "1PM24CS101", "branch": "CSE", "semester": 4, "cgpa": 12.0,
         "tenth_percentage": 81.0, "twelfth_percentage": 79.0, "backlog_history_count": 0},  # dup USN + bad range
    ])
    buf = io.BytesIO()
    batch.to_csv(buf, index=False)
    r = client.post("/api/tpo/import/validate", headers=hdr,
                    files={"file": ("batch.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 200
    d = r.json()
    assert d["rows_detected"] == 4
    assert d["valid_rows"] == 3
    assert d["new_students"] == 1
    assert d["update_rows"] == 2
    assert d["rejected_rows"] == 1
    job_id = d["job_id"]

    r = client.post(f"/api/tpo/import/confirm/{job_id}", headers=hdr)
    assert r.status_code == 200
    d2 = r.json()
    assert d2["imported_rows"] == 3
    assert d2["new_students"] == 1

    # confirm twice -> the job is no longer VALIDATED
    r = client.post(f"/api/tpo/import/confirm/{job_id}", headers=hdr)
    assert r.status_code == 404

    # academic record now reflects the imported CGPA (institution-only write path)
    from app.db.session import SessionLocal
    from app.models import AcademicRecord, Student
    from sqlalchemy import select
    db = SessionLocal()
    st = db.execute(select(Student).where(Student.usn == "1PM24CS101")).scalars().first()
    rec = db.execute(select(AcademicRecord).where(AcademicRecord.student_id == st.id)).scalars().first()
    assert rec.cgpa == 8.0

    # the unknown USN was created: student + user account + verified skill rows
    new_st = db.execute(select(Student).where(Student.usn == "1PM24CS999")).scalars().first()
    assert new_st is not None and new_st.user is not None
    skills = {s.skill.code: s for s in new_st.skills}
    assert skills["CODING"].score == 80 and skills["CODING"].status == "VERIFIED"
    db.close()


def test_import_template(client, tokens):
    r = client.get("/api/tpo/import/template", headers={"Authorization": f"Bearer {tokens['tpo']}"})
    assert r.status_code == 200
    assert b"usn" in r.content and b"cgpa" in r.content


def test_import_rejects_non_csv(client, tokens):
    r = client.post("/api/tpo/import/validate",
                    headers={"Authorization": f"Bearer {tokens['tpo']}"},
                    files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 200
    assert r.json()["status"] == "error"
