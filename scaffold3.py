import os

def write_file(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')

attendance_router_code = """
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from pydantic import BaseModel
from datetime import date
import uuid
from app.db.database import get_db
from app.core.security import get_current_user, get_admin_user
from app.models.models import User, AttendanceSession, AttendanceRecord, AttendanceStatus, AuditLog, FacultyAssignment

router = APIRouter()

class RecordIn(BaseModel):
    student_id: str
    status: AttendanceStatus

class SessionCreate(BaseModel):
    section_id: str
    subject_id: str
    date: date
    period: int
    records: List[RecordIn]

@router.post("/sessions")
def create_session(data: SessionCreate, db: Session = Depends(get_current_user)):
    # Very simplified: Admin can do everything, Faculty needs assignment check
    # Check assignment
    if db.role == "FACULTY":
        assignment = db.query(FacultyAssignment).filter_by(faculty_id=db.id, section_id=data.section_id, subject_id=data.subject_id).first()
        if not assignment:
            raise HTTPException(status_code=403, detail="Not assigned to this class")

    total_present = sum(1 for r in data.records if r.status == AttendanceStatus.PRESENT)
    total_absent = len(data.records) - total_present

    new_session = AttendanceSession(
        section_id=data.section_id,
        subject_id=data.subject_id,
        faculty_id=db.id,
        date=data.date,
        period=data.period,
        total_present=total_present,
        total_absent=total_absent
    )
    
    db.add(new_session)
    try:
        db.commit()
        db.refresh(new_session)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Session already exists")

    records_to_insert = [
        AttendanceRecord(
            session_id=new_session.id,
            student_id=r.student_id,
            status=r.status
        ) for r in data.records
    ]
    
    db.add_all(records_to_insert)
    db.commit()
    
    return {"message": "Attendance marked successfully", "session_id": new_session.id}

class RecordEdit(BaseModel):
    status: AttendanceStatus
    reason: str

@router.put("/records/{record_id}")
def edit_record(record_id: str, data: RecordEdit, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    record = db.query(AttendanceRecord).filter_by(id=record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
        
    old_status = record.status
    if old_status != data.status:
        record.status = data.status
        
        # Adjust session counts
        session = db.query(AttendanceSession).filter_by(id=record.session_id).first()
        if data.status == AttendanceStatus.PRESENT:
            session.total_present += 1
            session.total_absent -= 1
        else:
            session.total_present -= 1
            session.total_absent += 1
            
        # Audit Log
        audit = AuditLog(
            record_id=record.id,
            changed_by_user_id=current_user.id,
            old_status=old_status,
            new_status=data.status,
            reason=data.reason
        )
        db.add(audit)
        db.commit()
    return {"message": "Updated successfully"}
"""

def generate_step3():
    write_file("app/api/attendance.py", attendance_router_code)
    print("Step 3 scaffolding complete.")

if __name__ == "__main__":
    generate_step3()
