import pytest
import requests
import datetime

BASE_URL = "http://127.0.0.1:8000/api/v1"

@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    res = s.post(f"{BASE_URL}/auth/login", json={"email": "abhishek0157041@gmail.com", "password": "Aashu@123"})
    if res.status_code != 200:
        pytest.skip("Admin login failed, database might be empty")
    return s

def test_full_faculty_isolation_flow(admin_session):
    # 1. Admin creates core entities
    res1 = admin_session.post(f"{BASE_URL}/management/sections", json={"name": "CSE-A"}); print(res1.text); sec1 = res1(f"{BASE_URL}/management/sections", json={"name": "CSE-A"}).json()
    sec2 = admin_session.post(f"{BASE_URL}/management/sections", json={"name": "CSE-B"}).json()
    sub = admin_session.post(f"{BASE_URL}/management/subjects", json={"name": "DBMS", "code": "DB101"}).json()
    fac_a = admin_session.post(f"{BASE_URL}/management/faculty", json={"email": "facA@college.edu", "name": "FacA"}).json()
    fac_b = admin_session.post(f"{BASE_URL}/management/faculty", json={"email": "facB@college.edu", "name": "FacB"}).json()
    student = admin_session.post(f"{BASE_URL}/management/students", json={"name": "Bob", "email": "bob@stu.edu", "roll_number": "10101", "section_id": sec1['id']}).json()
    
    # 2. Assign FacA to Sec1
    admin_session.post(f"{BASE_URL}/management/assignments", json={
        "faculty_id": fac_a["id"],
        "section_id": sec1["id"],
        "subject_id": sub["id"]
    })
    
    # 3. Faculty A Login
    fac_a_sess = requests.Session()
    fac_a_sess.post(f"{BASE_URL}/auth/login", json={"email": "facA@college.edu", "password": "password123"})
    
    # 4. Faculty B Login
    fac_b_sess = requests.Session()
    fac_b_sess.post(f"{BASE_URL}/auth/login", json={"email": "facB@college.edu", "password": "password123"})
    
    # --- ISOLATION TESTS ---
    
    # FacA should be able to get students from Sec1
    assert fac_a_sess.get(f"{BASE_URL}/attendance/students/{sec1['id']}").status_code == 200
    
    # FacB should NOT be able to get students from Sec1 (403 Forbidden)
    assert fac_b_sess.get(f"{BASE_URL}/attendance/students/{sec1['id']}").status_code == 403
    
    # FacA marks attendance successfully
    payload = {
        "section_id": sec1["id"],
        "subject_id": sub["id"],
        "date": datetime.datetime.utcnow().isoformat(),
        "period": 1,
        "records": [{"student_id": student["id"], "status": "PRESENT"}]
    }
    att_res = fac_a_sess.post(f"{BASE_URL}/attendance/sessions", json=payload)
    assert att_res.status_code == 200
    session_id = att_res.json()["session_id"]
    
    # FacA cannot mark duplicate attendance
    dup_res = fac_a_sess.post(f"{BASE_URL}/attendance/sessions", json=payload)
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.text
    
    # FacB attempts to mark attendance in Sec1 (403 Forbidden)
    payload2 = {**payload, "period": 2}
    assert fac_b_sess.post(f"{BASE_URL}/attendance/sessions", json=payload2).status_code == 403
    
    print("ALL ISOLATION TESTS PASSED")
