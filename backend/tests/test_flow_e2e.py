"""
End-to-End Inter-Dashboard Flow Test:
1. Student expresses interest in an eligible drive.
2. HOD reviews and endorses the candidate with a recommendation note.
3. TPO views candidate with HOD endorsement and nominates them.
4. Student journey reflects all status transitions and endorsement notes in real time.
"""
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    Company,
    PlacementDrive,
    Department,
    Student,
    User,
)

def test_full_inter_dashboard_workflow(client):
    # Setup test drive and department mapping in test DB
    db = SessionLocal()
    try:
        dept = db.query(Department).filter(Department.code == "CSE").first()
        if not dept:
            dept = Department(code="CSE", name="Computer Science and Engineering", active=True)
            db.add(dept)
            db.flush()

        comp = db.query(Company).filter(Company.name == "E2E Tech Corp").first()
        if not comp:
            comp = Company(
                name="E2E Tech Corp",
                industry="Cloud & AI",
                location="Bengaluru",
                status="ACTIVE",
            )
            db.add(comp)
            db.flush()

        drive = db.query(PlacementDrive).filter(PlacementDrive.company_id == comp.id).first()
        if not drive:
            drive = PlacementDrive(
                company_id=comp.id,
                title="Graduate Cloud Engineer 2026",
                role="Cloud Engineer",
                status="OPEN",
                min_cgpa=6.0,
                max_backlogs=0,
                target_branches=["CSE", "ISE"],
                required_skills=["PYTHON", "SQL"],
            )
            db.add(drive)
            db.flush()

        # Check student
        st = db.query(Student).filter(Student.usn == "1PM24CS101").first()
        st.department_id = dept.id

        # Check/create HOD user
        hod_u = db.query(User).filter(User.email == "hod.cse@test.edu").first()
        if not hod_u:
            hod_u = User(
                role="DEPARTMENT",
                email="hod.cse@test.edu",
                password_hash=hash_password("Pass1234!"),
                display_name="Dr. CSE HOD",
                department_id=dept.id,
            )
            db.add(hod_u)

        db.commit()
        drive_id = drive.id
        student_id = st.id
    finally:
        db.close()

    # 1. Student Token via OTP
    r_otp = client.post("/api/auth/student/request-otp", json={"usn": "1PM24CS101"})
    assert r_otp.status_code == 200
    r_ver = client.post("/api/auth/student/verify-otp", json={"usn": "1PM24CS101", "otp": "246810"})
    assert r_ver.status_code == 200
    s_token = r_ver.json()["token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}

    # Find drives available for student
    res = client.get("/api/student/companies", headers=s_headers)
    assert res.status_code == 200
    opportunities = res.json()["opportunities"]
    assert len(opportunities) > 0

    # Student expresses interest
    res = client.post(f"/api/student/companies/{drive_id}/interest", headers=s_headers)
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    # 2. HOD Login (CSE)
    r_hod_login = client.post("/api/auth/staff/login", json={"email": "hod.cse@test.edu", "password": "Pass1234!"})
    assert r_hod_login.status_code == 200, r_hod_login.text
    hod_token = r_hod_login.json()["token"]
    hod_headers = {"Authorization": f"Bearer {hod_token}"}

    # HOD views placement status
    res = client.get("/api/dept/placements", headers=hod_headers)
    assert res.status_code == 200
    dept_data = res.json()
    assert dept_data["counts"]["pending_endorsement"] >= 1

    # Verify candidate is in the list
    c_list = [c for c in dept_data["rows"] if c["drive_id"] == drive_id and c["student_id"] == student_id]
    assert len(c_list) == 1
    candidate_id = c_list[0]["candidate_id"]
    assert c_list[0]["status"] == "INTERESTED"
    assert c_list[0]["can_endorse"] is True

    # HOD endorses student
    res = client.post(
        f"/api/dept/candidates/{candidate_id}/endorse",
        headers=hod_headers,
        json={"note": "Outstanding candidate in system architecture and coding. Strong recommendation!"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "ok"
    assert res.json()["candidate_status"] == "HOD_APPROVED"
    assert res.json()["hod_endorsed"] is True

    # 3. TPO Login
    r_tpo_login = client.post("/api/auth/staff/login", json={"email": "tpo@test.edu", "password": "Pass1234!"})
    assert r_tpo_login.status_code == 200
    tpo_token = r_tpo_login.json()["token"]
    tpo_headers = {"Authorization": f"Bearer {tpo_token}"}

    # TPO checks drive matching
    res = client.get(f"/api/tpo/matching/drives/{drive_id}", headers=tpo_headers)
    assert res.status_code == 200
    drive_matches = res.json()
    c_match = next((c for c in drive_matches["candidates"] if c["student_id"] == student_id), None)
    assert c_match is not None
    assert c_match["hod_endorsed"] is True
    assert "Outstanding candidate" in (c_match["hod_note"] or "")

    # TPO Nominates candidate
    res = client.post(
        f"/api/tpo/matching/drives/{drive_id}/nominate",
        headers=tpo_headers,
        json={"student_ids": [student_id]}
    )
    assert res.status_code == 200
    assert res.json()["nominated"] >= 1

    # 4. Student checks their Journey
    res = client.get("/api/student/placement-journey", headers=s_headers)
    assert res.status_code == 200
    journey = res.json()["journey"]
    app_entry = next((a for a in journey if a["drive_id"] == drive_id), None)
    assert app_entry is not None
    assert app_entry["status"] == "NOMINATED"
    assert app_entry["hod_endorsed"] is True
    assert "Outstanding candidate" in (app_entry["hod_note"] or "")

    print("SUCCESS: Full inter-dashboard cycle verified successfully!")
