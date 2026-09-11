"""Live end-to-end smoke test against a running CareerDNA API.

Run:  .venv/bin/python tests/e2e_smoke.py
Requires the server to be up on :8000 with a seeded DB.
"""
import json
import sys

import httpx

B = "http://127.0.0.1:8000"
c = httpx.Client(base_url=B, timeout=60)
PASS, FAIL = 0, 0


def check(name: str, cond: bool, extra: str = ""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok  {name} {extra}")
    else:
        FAIL += 1
        print(f" FAIL {name} {extra}")


def j(r):
    try:
        return r.json()
    except Exception:
        return {}


if "--reset" in sys.argv or "-r" in sys.argv:
    print("== 0. reseeding demo data ==")
    from scripts.seed_demo import main as seed_main
    seed_main(analysis=True, demo_students=True)

print("== 1. health ==")
r = c.get("/api/health")
check("health 200", r.status_code == 200)
check("model loaded", j(r).get("model") not in (None, "not_loaded"), j(r).get("model"))

print("== 2. student OTP login ==")
r = c.post("/api/auth/student/request-otp", json={"usn": "3PM24CS500"})
check("request-otp 200", r.status_code == 200, j(r).get("email_hint", ""))
r = c.post("/api/auth/student/verify-otp", json={"usn": "3PM24CS500", "otp": "246810"})
d = j(r)
check("verify-otp 200", r.status_code == 200)
ST = {"Authorization": f"Bearer {d['token']}"}
check("role student", d.get("user", {}).get("role") == "STUDENT")
check("usn roundtrip", d.get("user", {}).get("student", {}).get("usn") == "3PM24CS500")

r = c.post("/api/auth/student/verify-otp", json={"usn": "3PM24CS500", "otp": "000000"})
check("bad otp rejected", r.status_code in (400, 401, 429))

print("== 3. student readiness ==")
r = c.get("/api/student/readiness", headers=ST)
d = j(r)
check("readiness 200", r.status_code == 200)
check("status ok", d.get("status") == "ok")
p = d.get("prediction", {})
check("score present", isinstance(p.get("score"), (int, float)), f"score={p.get('score')} {p.get('category')}")
check("xai present", len(d.get("xai", {}).get("limiting", [])) > 0)
check("career target", d.get("career", {}).get("target_code") == "FULL_STACK")
base_score = p.get("score")
print(f"  Aarav baseline readiness: {base_score} ({p.get('category_label')})")

print("== 4. student passport / profile ==")
r = c.get("/api/student/passport", headers=ST)
d = j(r)
check("passport 200", r.status_code == 200)
check("passport has pending", d.get("passport", {}).get("counts", {}).get("PENDING", 0) >= 1,
      str(d.get("passport", {}).get("state")))
check("trust score", isinstance(d.get("trust", {}).get("score"), (int, float)))
r = c.get("/api/student/profile", headers=ST)
d = j(r)
check("academic immutable flag", d.get("academic", {}).get("editable") is False)

print("== 5. optimizer / what-if / roadmap ==")
r = c.get("/api/student/optimizer", headers=ST, params={"target_type": "GENERAL_READINESS"})
d = j(r)
check("optimizer 200", r.status_code == 200)
check("actions present", len(d.get("actions", [])) >= 1, f"-> {d.get('projected_readiness')}")
check("disclaimer present", "model" in d.get("disclaimer", "").lower())
r = c.get("/api/student/optimizer", headers=ST, params={"target_type": "CAREER_TRACK", "career_code": "FULL_STACK"})
d = j(r)
check("career optimizer 200", r.status_code == 200, f"career {d.get('baseline_career_match')} -> {d.get('projected_career_match')}")
r = c.post("/api/student/what-if/simulate", headers=ST,
           json={"changes": [{"feature": "sql_score", "value": 70}]})
d = j(r)
check("what-if 200", r.status_code == 200, f"{d.get('baseline_readiness')} -> {d.get('projected_readiness')}")
r = c.post("/api/student/what-if/simulate", headers=ST,
           json={"changes": [{"feature": "cgpa", "value": 9.5}]})
check("what-if rejects fixed feature", r.status_code == 400)
r = c.post("/api/student/roadmap/generate", headers=ST, json={"target_type": "GENERAL_READINESS"})
d = j(r)
rm = d.get("roadmap") or {}
check("roadmap generated", len(rm.get("items", [])) >= 1, f"items={len(rm.get('items', []))}")

print("== 6. faculty login + verification ==")
r = c.post("/api/auth/staff/login", json={
    "email": "kavya.raghavan@northfielddemo.edu", "password": "FacultyDemo123!"})
d = j(r)
check("faculty login", r.status_code == 200)
FAC = {"Authorization": f"Bearer {d['token']}"}
check("faculty categories", "PROJECT" in d.get("user", {}).get("categories", []))

r = c.get("/api/faculty/queue", headers=FAC,
          params={"category": "PROJECT", "status": "PENDING", "page": 1, "page_size": 100})
d = j(r)
check("queue 200", r.status_code == 200, f"total={d.get('total')}")
# The demo queue holds every seeded PENDING item, so search across pages.
aarav_req = None
pages = max(1, (d.get("total", 0) + 99) // 100)
for pg in range(1, min(pages, 20) + 1):
    if pg > 1:
        r = c.get("/api/faculty/queue", headers=FAC,
                  params={"category": "PROJECT", "status": "PENDING", "page": pg, "page_size": 100})
        d = j(r)
    aarav_req = next((q for q in d.get("items", []) if q.get("usn") == "3PM24CS500"), None)
    if aarav_req:
        break
check("Aarav pending project in queue", aarav_req is not None)

if aarav_req:
    rid = aarav_req["request_id"]
    r = c.get(f"/api/faculty/queue/{rid}", headers=FAC)
    d = j(r)
    check("queue detail 200", r.status_code == 200, d.get("item", {}).get("name", ""))
    r = c.post(f"/api/faculty/queue/{rid}/decide", headers=FAC,
               json={"decision": "VERIFIED", "note": "Evidence reviewed; project verified.",
                     "corrections": {"complexity": "Advanced"}})
    check("faculty verify decision", r.status_code == 200, j(r).get("decision", ""))

print("== 7. recompute after verification ==")
r = c.post("/api/student/readiness/refresh", headers=ST)
check("refresh 200", r.status_code == 200)
r = c.get("/api/student/readiness", headers=ST)
p2 = j(r).get("prediction", {})
new_score = p2.get("score")
print(f"  Aarav after verification: {new_score} ({p2.get('category_label')})")
check("readiness moved up on verification", (new_score or 0) > (base_score or 100),
      f"{base_score} -> {new_score}")

print("== 8. RBAC ==")
r = c.get("/api/tpo/overview", headers=ST)
check("student blocked from TPO", r.status_code == 403)
r = c.get("/api/faculty/queue", headers=ST)
check("student blocked from faculty", r.status_code == 403)
r = c.get("/api/student/readiness", headers=FAC)
check("faculty blocked from student", r.status_code == 403)
r = c.get("/api/tpo/overview")
check("anon blocked", r.status_code == 401)

# ops faculty (INTERNSHIP/ACTIVITY) must not verify PROJECT items
r = c.post("/api/auth/staff/login", json={
    "email": "rohit.deshmukh@northfielddemo.edu", "password": "FacultyDemo123!"})
FAC2 = {"Authorization": f"Bearer {j(r)['token']}"}
r = c.get("/api/faculty/queue", headers=FAC2, params={"category": "PROJECT"})
check("ops faculty cannot view PROJECT queue", r.status_code == 403)

print("== 9. TPO analytics ==")
r = c.post("/api/auth/staff/login", json={
    "email": "meera.iyer@northfielddemo.edu", "password": "TPOAdmin123!"})
d = j(r)
check("tpo login", r.status_code == 200)
TPO = {"Authorization": f"Bearer {d['token']}"}

r = c.get("/api/tpo/overview", headers=TPO)
d = j(r)
check("overview 200", r.status_code == 200, f"analyzed={d.get('population', {}).get('analyzed_students')}")
check("readiness dist", d.get("readiness", {}).get("ready_percentage") is not None)
check("branch metrics", len(d.get("branch_metrics", [])) >= 4)

r = c.get("/api/tpo/students", headers=TPO, params={"min_score": 0, "max_score": 59, "page_size": 5})
d = j(r)
check("vulnerable filter", d.get("total", 0) > 0, f"vulnerable={d.get('total')}")

r = c.get("/api/tpo/skills", headers=TPO)
d = j(r)
check("heatmap data", len(d.get("heatmap", [])) > 10, f"cells={len(d.get('heatmap', []))}")
top_skill = d.get("deficits", [{}])[0].get("skill")
r = c.get(f"/api/tpo/skills/{top_skill}/drilldown", headers=TPO)
d = j(r)
check("skill drilldown", r.status_code == 200 and d.get("count", 0) > 0,
      f"{top_skill} n={d.get('count')}")

r = c.get("/api/tpo/cohorts/vulnerable", headers=TPO)
d = j(r)
check("vulnerable cohorts", len(d.get("cohorts", [])) >= 1)

print("== 10. TPO interventions ==")
r = c.get("/api/tpo/interventions", headers=TPO)
d = j(r)
ivs = d.get("interventions", [])
check("interventions ranked", len(ivs) >= 3, f"top={ivs[0]['name'] if ivs else None}")
iv0 = ivs[0]
r = c.post("/api/tpo/interventions/simulate", headers=TPO,
           json={"intervention_code": iv0["code"], "improvement": 20})
d = j(r)
check("intervention simulation", r.status_code == 200,
      f"n={d.get('simulation', {}).get('cohort_size')} moved={d.get('simulation', {}).get('students_moving_category')}")
check("simulation disclaimer", "projection" in d.get("disclaimer", "").lower())
r = c.get(f"/api/tpo/interventions/{iv0['code']}/cohort", headers=TPO)
d = j(r)
check("intervention cohort list", len(d.get("students", [])) > 0)

print("== 11. TPO import ==")
import pandas as pd, io
from pathlib import Path
_data_path = Path(__file__).resolve().parents[2] / "datasets" / "institution_master_demo.csv"
df = pd.read_csv(_data_path)
sub = df.head(25).copy()
# perturb one row to force a rejection
sub.loc[2, "cgpa"] = 12.5
buf = io.BytesIO()
sub.to_csv(buf, index=False)
r = c.post("/api/tpo/import/validate", headers=TPO,
           files={"file": ("batch.csv", buf.getvalue(), "text/csv")})
d = j(r)
check("import validate", r.status_code == 200,
      f"valid={d.get('valid_rows')} rejected={d.get('rejected_rows')}")
job_id = d.get("job_id")
r = c.post(f"/api/tpo/import/confirm/{job_id}", headers=TPO)
d = j(r)
check("import confirm", r.status_code == 200, f"imported={d.get('imported_rows')}")
r = c.get("/api/tpo/import/jobs", headers=TPO)
d = j(r)
check("import jobs list", len(d.get("jobs", [])) >= 1)

print("== 11.5 placement management (companies, drives, matching, pipeline) ==")
r = c.get("/api/tpo/companies", headers=TPO)
d = j(r)
companies = d.get("companies", [])
check("seeded companies", len(companies) >= 5, f"n={len(companies)}")

r = c.get("/api/tpo/drives", headers=TPO)
d = j(r)
drives = d.get("drives", [])
open_drives = [x for x in drives if x["status"] == "OPEN"]
check("open drives", len(open_drives) >= 5, f"n={len(open_drives)}")

# --- candidate matching (TPO flagship) ---
drive = next(x for x in open_drives if x["company"] == "VerveTech Solutions")
r = c.get(f"/api/tpo/matching/drives/{drive['id']}", headers=TPO)
d = j(r)
cands = d.get("candidates", [])
check("matching evaluated", len(cands) > 10, f"n={len(cands)}")
elig = [x for x in cands if x["eligible"]]
check("eligible ranked first", bool(cands) and cands[0]["eligible"],
      f"top={cands[0]['usn'] if cands else None}")
check("weights documented (sum 1.0)", abs(sum(d.get("weights", {}).values()) - 1.0) < 1e-9)
check("pipeline consistent", d.get("pipeline", {}).get("eligible") == len(elig))
check("eligibility has blockers detail",
      all(isinstance(x.get("mandatory_blockers"), list) for x in cands))

target = elig[0] if elig else None
check("has eligible candidate", target is not None)
nominated_id = None
if target:
    r = c.post(f"/api/tpo/matching/drives/{drive['id']}/nominate", headers=TPO,
               json={"student_ids": [target["student_id"]], "note": "e2e nomination"})
    d = j(r)
    check("nomination recorded", r.status_code == 200 and d.get("nominated") == 1,
          f"skipped={d.get('skipped')}")
    nominated_id = target["student_id"]
    inelig = next((x for x in cands if not x["eligible"]), None)
    if inelig:
        r = c.post(f"/api/tpo/matching/drives/{drive['id']}/nominate", headers=TPO,
                   json={"student_ids": [inelig["student_id"]]})
        d = j(r)
        check("ineligible nomination blocked",
              r.status_code == 200 and d.get("nominated") == 0 and d.get("skipped"))

# --- company recruiter ---
r = c.post("/api/auth/staff/login", json={
    "email": "priya.nair@vervetech-demo.example", "password": "RecruiterDemo123!"})
check("recruiter login", r.status_code == 200)
REC = {"Authorization": f"Bearer {j(r)['token']}"}
r = c.get("/api/company/overview", headers=REC)
d = j(r)
check("company overview", r.status_code == 200 and d.get("company", {}).get("name") == "VerveTech Solutions")
r = c.get(f"/api/company/drives/{drive['id']}/candidates", headers=REC)
d = j(r)
rows = d.get("rows", [])
check("nominated visible to company",
      nominated_id is not None and any(x["student_id"] == nominated_id for x in rows),
      f"rows={len(rows)}")
detail = c.get(f"/api/company/drives/{drive['id']}/candidates/{nominated_id}", headers=REC)
dd = j(detail)
check("candidate detail 200", detail.status_code == 200 and dd.get("student"))
leaked = set()
def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in ("email", "email_hint", "storage_path", "file_path"):
                leaked.add(k)
            _walk(v)
    elif isinstance(o, list):
        for v in o:
            _walk(v)
_walk(dd)
check("no private fields leaked", not leaked, f"leaked={leaked}")

# cross-company isolation
r2c = c.post("/api/auth/staff/login", json={
    "email": "arjun.kulkarni@databridge-demo.example", "password": "RecruiterDemo123!"})
REC2 = {"Authorization": f"Bearer {j(r2c)['token']}"}
other_drive = j(c.get("/api/company/drives", headers=REC2)).get("drives", [{}])[0].get("id")
r = c.get(f"/api/company/drives/{drive['id']}/candidates", headers=REC2)
check("cross-company drive access denied", r.status_code == 403)
r = c.get("/api/company/drives", headers=REC2)
names = {x.get("title") for x in j(r).get("drives", [])}
check("company sees only own drives", len(names) == 1)

# --- student side ---
r = c.get("/api/student/companies", headers=ST)
d = j(r)
opps = d.get("opportunities", [])
check("student sees opportunities", r.status_code == 200 and len(opps) >= 1, f"n={len(opps)}")
check("opportunity explanations present",
      all(isinstance(o.get("explanation"), list) and o.get("explanation") for o in opps[:3]))
check("opportunity eligibility+match distinct",
      all(("eligible" in o and "match_score" in o) for o in opps[:3]))
r = c.get("/api/student/placement-journey", headers=ST)
check("student journey 200", r.status_code == 200 and "journey" in j(r))

# --- pipeline: shortlist -> interview -> select -> TPO confirm ---
if nominated_id:
    r = c.post(f"/api/company/drives/{drive['id']}/candidates/{nominated_id}/status",
               headers=REC, json={"status": "SHORTLISTED", "note": "good paper round"})
    check("company shortlists", r.status_code == 200 and j(r).get("candidate_status") == "SHORTLISTED")
    r = c.post(f"/api/company/drives/{drive['id']}/candidates/{nominated_id}/status",
               headers=REC, json={"status": "SELECTED", "note": "strong interview"})
    check("company selects", r.status_code == 200 and j(r).get("candidate_status") == "SELECTED")
    # company cannot confirm
    r = c.get("/api/tpo/placements", headers=REC)
    check("company blocked from placements", r.status_code == 403)
    # TPO confirms
    r = c.get("/api/tpo/placements", headers=TPO)
    d = j(r)
    row = next((x for x in d.get("rows", []) if x["student_id"] == nominated_id), None)
    check("selected visible to TPO", row is not None and row["status"] == "SELECTED")
    if row:
        r = c.post(f"/api/tpo/placements/{row['candidate_id']}/confirm", headers=TPO,
                   json={"note": "e2e confirmation"})
        check("TPO confirms placement", r.status_code == 200 and j(r).get("status") == "PLACED")
    # invalid transition guard
    r = c.post(f"/api/company/drives/{drive['id']}/candidates/{nominated_id}/status",
               headers=REC, json={"status": "SHORTLISTED"})
    check("terminal transition blocked", r.status_code == 409)

# --- department scope ---
r = c.post("/api/auth/staff/login", json={
    "email": "dept.cse@northfielddemo.edu", "password": "DeptDemo123!"})
check("department login", r.status_code == 200)
DEPT = {"Authorization": f"Bearer {j(r)['token']}"}
r = c.get("/api/dept/overview", headers=DEPT)
d = j(r)
check("dept overview scoped", r.status_code == 200 and d.get("department") == "CSE",
      f"students={len(d.get('students', []))}")
cse_students = d.get("students", [])
check("dept students analyzed", d.get("population", {}).get("analyzed", 0) >= 100,
      f"analyzed={d.get('population', {}).get('analyzed')}")
r = c.post("/api/auth/staff/login", json={
    "email": "dept.ise@northfielddemo.edu", "password": "DeptDemo123!"})
DEPT2 = {"Authorization": f"Bearer {j(r)['token']}"}
d2 = j(c.get("/api/dept/overview", headers=DEPT2))
ise_ids = {s["student_id"] for s in d2.get("students", [])}
cse_ids = {s["student_id"] for s in cse_students}
check("departments disjoint", not (ise_ids & cse_ids))
if cse_students:
    r = c.post(f"/api/dept/students/{cse_students[0]['student_id']}",
               headers=DEPT2, json={"updates": {"cgpa": 9.9}})
    check("cross-dept data update blocked", r.status_code == 403)
r = c.get("/api/dept/companies", headers=DEPT)
d = j(r)
check("dept company eligibility", r.status_code == 200 and len(d.get("drives", [])) >= 1,
      f"drives={len(d.get('drives', []))}")

# --- verification center (TPO oversight) ---
r = c.get("/api/tpo/verification-center", headers=TPO)
d = j(r)
check("verification center", r.status_code == 200 and "counts" in d)
r = c.get("/api/tpo/verifiers", headers=TPO)
d = j(r)
verifiers = d.get("verifiers", [])
check("verifiers listed", len(verifiers) >= 2, f"n={len(verifiers)}")

print("== 12. model info ==")
r = c.get("/api/model/info", headers=TPO)
d = j(r)
check("model info 200", r.status_code == 200)
check("metrics present", "f1" in d.get("selected_metrics", {}))
check("global importance", len(d.get("global_importance", {})) >= 10)
check("feature list", len(d.get("features", [])) == 23)

print(f"\n===== RESULT: {PASS} passed, {FAIL} failed =====")
sys.exit(1 if FAIL else 0)
