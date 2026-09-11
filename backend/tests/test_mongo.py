"""Tests for MongoDB document storage and activity logging."""
from app.db import mongo


def test_health_with_mongodb(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert "mongodb" in body
    assert "status" in body["mongodb"]


def test_student_resume_document_flow(client):
    # Authenticate student
    client.post("/api/auth/student/request-otp", json={"usn": "1PM24CS101"})
    r_ver = client.post("/api/auth/student/verify-otp", json={"usn": "1PM24CS101", "otp": "246810"})
    token = r_ver.json()["token"]
    student_id = r_ver.json()["user"]["student"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Save resume
    resume_payload = {
        "summary": "Final year CS student passionate about distributed systems and cloud architecture.",
        "skills": ["Python", "FastAPI", "MongoDB", "React", "Docker"],
        "education": [
            {"institution": "Northfield Institute of Technology", "degree": "B.Tech CSE", "year": 2026}
        ],
        "projects": [
            {"title": "CareerDNA Engine", "description": "AI placement matching platform with dual data stores"}
        ],
    }
    res = client.post("/api/documents/student/resume", json=resume_payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["document"]["doc_type"] == "RESUME"

    # Get resume
    res = client.get(f"/api/documents/student/{student_id}/resume", headers=headers)
    assert res.status_code == 200
    doc = res.json()["document"]
    assert doc is not None
    assert doc["resume_data"]["summary"].startswith("Final year CS student")


def test_student_portfolio_document_flow(client):
    client.post("/api/auth/student/request-otp", json={"usn": "1PM24CS101"})
    r_ver = client.post("/api/auth/student/verify-otp", json={"usn": "1PM24CS101", "otp": "246810"})
    token = r_ver.json()["token"]
    student_id = r_ver.json()["user"]["student"]["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Add portfolio item
    portfolio_payload = {
        "item_type": "project_case_study",
        "title": "High-Throughput ML Pipeline",
        "description": "Designed asynchronous model serving pipeline processing 10k requests/sec",
        "tech_stack": ["Python", "FastAPI", "MongoDB", "Redis"],
        "media_urls": ["https://demo.cdn/architecture-diagram.png"],
    }
    res = client.post("/api/documents/student/portfolio", json=portfolio_payload, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # Get portfolio items
    res = client.get(f"/api/documents/student/{student_id}/portfolio", headers=headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) >= 1
    assert items[0]["item_data"]["title"] == "High-Throughput ML Pipeline"


def test_activity_logging_and_fetch(client):
    # Log direct event
    mongo.log_activity(
        action="TEST_EVENT",
        actor_id=1,
        actor_role="TPO_ADMIN",
        target_type="SYSTEM",
        details={"info": "Test MongoDB activity logging"},
    )

    # Login as TPO staff
    r_login = client.post("/api/auth/staff/login", json={"email": "tpo@test.edu", "password": "Pass1234!"})
    tpo_token = r_login.json()["token"]
    tpo_headers = {"Authorization": f"Bearer {tpo_token}"}

    # Query activity logs
    res = client.get("/api/documents/activity-logs", headers=tpo_headers)
    assert res.status_code == 200
    logs = res.json()["logs"]
    assert len(logs) > 0
    test_log = next((l for l in logs if l.get("action") == "TEST_EVENT"), None)
    assert test_log is not None
