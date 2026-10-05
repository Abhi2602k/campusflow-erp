# from fastapi import APIRouter, Depends
# from sqlalchemy.orm import Session
# from app.db.database import get_db
# from app.core.security import get_current_user, get_admin_user, get_admin_or_pl_user
# from app.models.models import User, Student, FacultyAssignment, AttendanceSession, AttendanceRecord, RoleEnum
#
# router = APIRouter()
#
# @router.get("/admin")
# def get_admin_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_admin_or_pl_user)):
#     total_students = db.query(Student).count()
#     total_faculty = db.query(User).filter(User.role == RoleEnum.FACULTY).count()
#     total_sessions = db.query(AttendanceSession).count()
#
#     return {
#         "total_students": total_students,
#         "total_faculty": total_faculty,
#         "today_attendance": {"marked": total_sessions, "pending": 0},
#         "average_attendance_percentage": 0,
#         "low_attendance_count": 0,
#         "recent_sessions": []
#     }
#
# @router.get("/faculty")
# def get_faculty_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
#     assigned_classes = db.query(FacultyAssignment).filter(FacultyAssignment.faculty_id == current_user.id).count()
#     return {
#         "assigned_classes": assigned_classes,
#         "assigned_subjects": assigned_classes,
#         "today_attendance": {"marked": 0, "pending": 0},
#         "recent_sessions": [],
#         "low_attendance_count": 0
#     }
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.database import get_db
from app.core.security import (
    get_current_user,
    get_admin_user,
    get_admin_or_pl_user,
)
from app.models.models import (
    User,
    Student,
    FacultyAssignment,
    AttendanceSession,
    AttendanceRecord,
    RoleEnum,
)

router = APIRouter()


@router.get("/admin")
async def get_admin_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_admin_or_pl_user),
):
    result = await db.execute(
        select(func.count()).select_from(Student)
    )
    total_students = result.scalar() or 0

    result = await db.execute(
        select(func.count())
        .select_from(User)
        .where(User.role == RoleEnum.FACULTY)
    )
    total_faculty = result.scalar() or 0

    result = await db.execute(
        select(func.count())
        .select_from(AttendanceSession)
    )
    total_sessions = result.scalar() or 0

    return {
        "total_students": total_students,
        "total_faculty": total_faculty,
        "today_attendance": {
            "marked": total_sessions,
            "pending": 0
        },
        "average_attendance_percentage": 0,
        "low_attendance_count": 0,
        "recent_sessions": []
    }


@router.get("/faculty")
async def get_faculty_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(func.count())
        .select_from(FacultyAssignment)
        .where(
            FacultyAssignment.faculty_id == current_user.id
        )
    )

    assigned_classes = result.scalar() or 0

    return {
        "assigned_classes": assigned_classes,
        "assigned_subjects": assigned_classes,
        "today_attendance": {
            "marked": 0,
            "pending": 0
        },
        "recent_sessions": [],
        "low_attendance_count": 0
    }