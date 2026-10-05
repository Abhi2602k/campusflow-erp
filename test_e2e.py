import requests
import pytest
from app.db.database import SessionLocal
from app.models.models import User, Student, Subject, AttendanceSession, AttendanceRecord

BASE_URL = "http://127.0.0.1:8000/api/v1"
session = requests.Session()

def test_01_admin_login():
    res = session.post(f"{BASE_URL}/auth/login", json={"email": "abhishek0157041@gmail.com", "password": "Aashu@123"})
    assert res.status_code == 200
    assert "Login successful" in res.text
    
def test_02_admin_dashboard():
    res = session.get(f"{BASE_URL}/dashboard/admin")
    assert res.status_code == 200
    data = res.json()
    assert "total_students" in data

def test_03_create_student():
    res = session.post(f"{BASE_URL}/management/students", json={
        "name": "Test Student",
        "roll_number": "CS101",
        "email": "test@student.com"
    })
    assert res.status_code == 200
    assert res.json()["name"] == "Test Student"

def test_04_create_subject():
    res = session.post(f"{BASE_URL}/management/subjects", json={
        "name": "DBMS",
        "code": "CS401"
    })
    assert res.status_code == 200
    
def test_05_unauthorized_access():
    anon_session = requests.Session()
    res = anon_session.get(f"{BASE_URL}/dashboard/admin")
    assert res.status_code == 401

if __name__ == "__main__":
    pytest.main(["-v", "test_e2e.py"])
