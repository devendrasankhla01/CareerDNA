"""Auth tests: USN→OTP flow, staff login, sessions, rate limiting."""


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] == "ok"
    assert body["model"] not in (None, "not_loaded")


def test_student_otp_flow(client):
    r = client.post("/api/auth/student/request-otp", json={"usn": "1PM24CS101"})
    assert r.status_code == 200
    body = r.json()
    assert body["demo_otp"] == "246810"
    assert "@" in body["email_hint"] and "1PM24CS101" not in body["email_hint"].upper()

    r = client.post("/api/auth/student/verify-otp",
                    json={"usn": "1PM24CS101", "otp": "246810"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "STUDENT"
    assert body["user"]["student"]["usn"] == "1PM24CS101"
    assert len(body["token"]) >= 30


def test_student_otp_unknown_usn(client):
    client.post("/api/auth/student/request-otp", json={"usn": "9PM24XX999"})
    r = client.post("/api/auth/student/verify-otp", json={"usn": "9PM24XX999", "otp": "246810"})
    assert r.status_code == 404


def test_student_otp_wrong_code(client):
    client.post("/api/auth/student/request-otp", json={"usn": "1PM24IS102"})
    r = client.post("/api/auth/student/verify-otp", json={"usn": "1PM24IS102", "otp": "111111"})
    assert r.status_code in (400, 401)


def test_student_cannot_login_via_staff_endpoint(client):
    r = client.post("/api/auth/staff/login",
                    json={"email": "1pm24cs101@northfielddemo.edu", "password": "x" * 8})
    assert r.status_code in (401, 429)


def test_staff_login_and_me(client, tokens):
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['tpo']}"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "TPO_ADMIN"


def test_logout_revokes_token(client):
    r = client.post("/api/auth/student/request-otp", json={"usn": "1PM24CS101"})
    r = client.post("/api/auth/student/verify-otp", json={"usn": "1PM24CS101", "otp": "246810"})
    token = r.json()["token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    r = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_missing_token_rejected(client):
    assert client.get("/api/student/readiness").status_code == 401
    assert client.get("/api/student/readiness",
                      headers={"Authorization": "Bearer bogus"}).status_code == 401
