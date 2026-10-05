import os
from sqlalchemy import create_engine
from app.models.models import Base, User, RoleEnum
from app.db.database import engine, SessionLocal
from app.core.security import get_password_hash

# 1. Clean the old database to apply the new schema
if os.path.exists('attendance.db'):
    try:
        os.remove('attendance.db')
    except Exception as e:
        print('Could not remove db:', e)

# 2. Re-create all tables with new constraints
Base.metadata.create_all(bind=engine)

# 3. Seed the admin user again
db = SessionLocal()
admin = User(
    email='abhishek0157041@gmail.com',
    hashed_password=get_password_hash('Aashu@123'),
    role=RoleEnum.ADMIN,
    name='Abhishek Admin'
)
db.add(admin)
db.commit()
print('Database cleanly recreated and seeded!')
