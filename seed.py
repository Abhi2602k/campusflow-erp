import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.db.database import SessionLocal
from app.models.models import User, RoleEnum, Base
from app.db.database import engine
Base.metadata.create_all(bind=engine)
from app.core.security import get_password_hash

def seed_users():
    db = SessionLocal()
    # Check if admin exists
    admin = db.query(User).filter_by(email="admin@college.edu").first()
    if not admin:
        admin = User(
            email="admin@college.edu",
            hashed_password=get_password_hash("admin123"),
            role=RoleEnum.ADMIN,
            name="Super Admin"
        )
        db.add(admin)
    
    # Check if faculty exists
    faculty = db.query(User).filter_by(email="faculty@college.edu").first()
    if not faculty:
        faculty = User(
            email="faculty@college.edu",
            hashed_password=get_password_hash("faculty123"),
            role=RoleEnum.FACULTY,
            name="Test Faculty"
        )
        db.add(faculty)
    
    db.commit()
    print("Seed users created. admin@college.edu (admin123) / faculty@college.edu (faculty123)")

if __name__ == "__main__":
    seed_users()
