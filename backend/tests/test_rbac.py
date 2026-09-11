"""Authorization tests: every role boundary is enforced server-side."""


def test_student_cannot_access_tpo(client, tokens):
    r = client.get("/api/tpo/overview", headers={"Authorization": f"Bearer {tokens['student']}"})
    assert r.status_code == 403


def test_student_cannot_access_faculty_queue(client, tokens):
    r = client.get("/api/faculty/queue", headers={"Authorization": f"Bearer {tokens['student']}"})
    assert r.status_code == 403


def test_student_cannot_modify_another_student_data(client, tokens):
    # student A attempts to resubmit student B's project (entity id 1 belongs to Test Beta)
    r = client.post("/api/student/evidence/resubmit/project/1",
                    headers={"Authorization": f"Bearer {tokens['student']}"})
    assert r.status_code in (403, 404)


def test_faculty_cannot_access_student_endpoints(client, tokens):
    r = client.get("/api/student/readiness", headers={"Authorization": f"Bearer {tokens['faculty_proj']}"})
    assert r.status_code == 403
    r = client.get("/api/student/passport", headers={"Authorization": f"Bearer {tokens['faculty_proj']}"})
    assert r.status_code == 403


def test_faculty_cannot_access_tpo(client, tokens):
    r = client.get("/api/tpo/overview", headers={"Authorization": f"Bearer {tokens['faculty_proj']}"})
    assert r.status_code == 403
    r = client.get("/api/tpo/interventions", headers={"Authorization": f"Bearer {tokens['faculty_intern']}"})
    assert r.status_code == 403


def test_faculty_category_scope_view(client, tokens):
    # faculty_intern is scoped to INTERNSHIP only -> PROJECT queue must be denied
    r = client.get("/api/faculty/queue", params={"category": "PROJECT"},
                   headers={"Authorization": f"Bearer {tokens['faculty_intern']}"})
    assert r.status_code == 403


def test_faculty_category_scope_decide(client, tokens):
    # find the pending PROJECT request (Test Beta)
    r = client.get("/api/faculty/queue", params={"category": "PROJECT"},
                   headers={"Authorization": f"Bearer {tokens['faculty_proj']}"})
    items = r.json().get("items", [])
    assert len(items) >= 1
    req = next(i for i in items if i["student_id"])
    rid = req["request_id"]
    # the wrong-category faculty may not view it
    r2 = client.get(f"/api/faculty/queue/{rid}",
                    headers={"Authorization": f"Bearer {tokens['faculty_intern']}"})
    assert r2.status_code == 403


def test_anonymous_access_denied(client):
    for path in ("/api/student/readiness", "/api/tpo/overview",
                 "/api/faculty/queue", "/api/model/info"):
        assert client.get(path).status_code == 401, path


def test_no_public_registration(client):
    assert client.post("/api/auth/register", json={}).status_code == 404
