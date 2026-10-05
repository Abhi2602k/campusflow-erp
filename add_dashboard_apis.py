import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')

dashboard_api_code = """
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.core.security import get_current_user, get_admin_user
from app.models.models import User, Student, FacultyAssignment, AttendanceSession, AttendanceRecord, RoleEnum

router = APIRouter()

@router.get("/admin")
def get_admin_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    total_students = db.query(Student).count()
    total_faculty = db.query(User).filter(User.role == RoleEnum.FACULTY).count()
    total_sessions = db.query(AttendanceSession).count()
    
    return {
        "total_students": total_students,
        "total_faculty": total_faculty,
        "today_attendance": {"marked": total_sessions, "pending": 0},
        "average_attendance_percentage": 0,
        "low_attendance_count": 0,
        "recent_sessions": []
    }

@router.get("/faculty")
def get_faculty_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    assigned_classes = db.query(FacultyAssignment).filter(FacultyAssignment.faculty_id == current_user.id).count()
    return {
        "assigned_classes": assigned_classes,
        "assigned_subjects": assigned_classes,
        "today_attendance": {"marked": 0, "pending": 0},
        "recent_sessions": [],
        "low_attendance_count": 0
    }
"""

main_update_code = """
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.attendance import router as attendance_router
from app.api.dashboard import router as dashboard_router

app = FastAPI(title="College Attendance ERP")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(attendance_router, prefix="/api/v1/attendance", tags=["attendance"])
app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["dashboard"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
"""

def apply():
    write_file("app/api/dashboard.py", dashboard_api_code)
    write_file("app/main.py", main_update_code)
    print("Dashboard APIs added.")

if __name__ == "__main__":
    apply()
