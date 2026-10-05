from sqlalchemy import create_engine
from app.models.models import Base, User, RoleEnum, AcademicYear, CourseClass, Branch, Section, Subject, FacultyAssignment, AttendanceSession, AttendanceRecord, AttendanceAuditLog
from app.db.database import engine, SessionLocal
from app.core.security import get_password_hash
import uuid

# Drop all tables and recreate
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

admin = User(email='abhishek0157041@gmail.com', hashed_password=get_password_hash('Aashu@123'), role=RoleEnum.ADMIN, name='Abhishek Admin')
db.add(admin)

fac1 = User(email='rahul1@college.com', hashed_password=get_password_hash('password123'), role=RoleEnum.FACULTY, name='Rahul Kumar')
fac2 = User(email='rahul2@college.com', hashed_password=get_password_hash('password123'), role=RoleEnum.FACULTY, name='Rahul Kumar')
db.add(fac1)
db.add(fac2)

ay = AcademicYear(id=str(uuid.uuid4()), name='2026-27')
db.add(ay)

btech = CourseClass(id=str(uuid.uuid4()), name='B.Tech')
db.add(btech)

cse = Branch(id=str(uuid.uuid4()), name='CSE')
ece = Branch(id=str(uuid.uuid4()), name='ECE')
db.add(cse)
db.add(ece)

secA = Section(id=str(uuid.uuid4()), name='A')
secB = Section(id=str(uuid.uuid4()), name='B')
db.add(secA)
db.add(secB)

sub1 = Subject(id=str(uuid.uuid4()), name='Computer Networks', code='CN101')
sub2 = Subject(id=str(uuid.uuid4()), name='DBMS', code='DB101')
db.add(sub1)
db.add(sub2)

db.commit()
print("Clean DB seeded successfully.")
