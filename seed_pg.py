import asyncio
import sys
import os
import uuid
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal
from app.models.models import User, RoleEnum
from app.core.security import pwd_context

async def seed_superadmin():
    async with SessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.email == "abhi2602k@gmail.com"))
        existing_user = result.scalars().first()
        
        if not existing_user:
            print("Creating superadmin user...")
            superadmin = User(
                id=str(uuid.uuid4()),
                email="abhi2602k@gmail.com",
                hashed_password=pwd_context.hash("Aashu@123"),
                name="Abhi (Superadmin)",
                role=RoleEnum.SUPERADMIN,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(superadmin)
            await db.commit()
            print("Superadmin created successfully.")
        else:
            print("Superadmin already exists.")

if __name__ == "__main__":
    asyncio.run(seed_superadmin())
