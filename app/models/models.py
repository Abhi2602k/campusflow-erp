from sqlalchemy import Column, String, Boolean, ForeignKey, DateTime, Float, Integer, UniqueConstraint, Enum, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.db.database import Base
import uuid

class RoleEnum(str, enum.Enum):
    SUPERADMIN = "SUPERADMIN"
    ADMIN = "ADMIN"
    FACULTY = "FACULTY"
    STUDENT = "STUDENT"
    PROGRAM_LEADER = "PROGRAM_LEADER"

class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT = "ABSENT"

class User(Base):
    __tablename__ = "users"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(Enum(RoleEnum))
    name = Column(String(255))
    employee_code = Column(String(100), nullable=True)
    department = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AcademicYear(Base):
    __tablename__ = "academic_years"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True)

class CourseClass(Base):
    __tablename__ = "course_classes"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True)

class Branch(Base):
    __tablename__ = "branches"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True)

class Section(Base):
    __tablename__ = "sections"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255))

class Subject(Base):
    __tablename__ = "subjects"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255))
    code = Column(String(255), unique=True)

class Student(Base):
    __tablename__ = "students"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    name = Column(String(255))
    enrollment_no = Column(String(255), unique=True)
    roll_number = Column(String(255), unique=True, nullable=True)
    email = Column(String(255), unique=True)
    class_id = Column(String(36), ForeignKey("course_classes.id"))
    year = Column(String(50))
    branch_id = Column(String(36), ForeignKey("branches.id"))
    section_id = Column(String(36), ForeignKey("sections.id"))
    is_active = Column(Boolean, default=True)

class FacultyAssignment(Base):
    __tablename__ = "faculty_assignments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    faculty_id = Column(String(36), ForeignKey("users.id"))
    academic_year_id = Column(String(36), ForeignKey("academic_years.id"))
    class_id = Column(String(36), ForeignKey("course_classes.id"))
    year = Column(String(50))
    branch_id = Column(String(36), ForeignKey("branches.id"))
    section_id = Column(String(36), ForeignKey("sections.id"))
    subject_id = Column(String(36), ForeignKey("subjects.id"))
    
    __table_args__ = (
        UniqueConstraint('academic_year_id', 'class_id', 'year', 'branch_id', 'section_id', 'subject_id', 'faculty_id', name='uix_full_assignment'),
    )

class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    section_id = Column(String(36), ForeignKey("sections.id"))
    subject_id = Column(String(36), ForeignKey("subjects.id"))
    faculty_id = Column(String(36), ForeignKey("users.id"))
    date = Column(DateTime)
    start_time = Column(String(10))
    end_time = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('section_id', 'subject_id', 'date', 'start_time', 'end_time', name='uix_attendance_session'),
    )

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("attendance_sessions.id"))
    student_id = Column(String(36), ForeignKey("students.id"))
    status = Column(Enum(AttendanceStatus))
    
    __table_args__ = (
        UniqueConstraint('session_id', 'student_id', name='uix_attendance_record'),
    )

class AttendanceAuditLog(Base):
    __tablename__ = "attendance_audit_logs"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_id = Column(String(36), ForeignKey("attendance_records.id"))
    changed_by = Column(String(36), ForeignKey("users.id"))
    old_status = Column(String(50))
    new_status = Column(String(50))
    reason = Column(String(255))
    timestamp = Column(DateTime, default=datetime.utcnow)

class ProgramLeaderAssignment(Base):
    __tablename__ = "program_leader_assignments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), unique=True)
    class_id = Column(String(36), ForeignKey("course_classes.id"))
    year = Column(String(50))
    branch_id = Column(String(36), ForeignKey("branches.id"))
    section_id = Column(String(36), ForeignKey("sections.id"))



class Notice(Base):
    __tablename__ = "notices"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pl_id = Column(String(36), ForeignKey("users.id"))
    title = Column(String(255))
    content = Column(Text)
    audience = Column(String(50)) # 'STUDENTS', 'FACULTY', 'BOTH'
    class_id = Column(String(36), ForeignKey("course_classes.id"))
    year = Column(String(50))
    branch_id = Column(String(36), ForeignKey("branches.id"))
    section_id = Column(String(36), ForeignKey("sections.id"))
    attachment_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Assessment(Base):
    __tablename__ = "assessments"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subject_id = Column(String, ForeignKey("subjects.id"))
    section_id = Column(String, ForeignKey("sections.id"))
    name = Column(String)
    type = Column(String)
    sequence_number = Column(Integer)
    max_marks = Column(Float)
    date = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class StudentMark(Base):
    __tablename__ = "student_marks"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    assessment_id = Column(String, ForeignKey("assessments.id"))
    student_id = Column(String, ForeignKey("students.id"))
    marks_obtained = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
