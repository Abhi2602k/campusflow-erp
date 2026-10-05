from app.db.database import SessionLocal
from app.models.models import User, RoleEnum
from app.core.security import get_password_hash
import uuid

db = SessionLocal()

# Check if superadmin exists
superadmin = db.query(User).filter_by(email="abhi2602k@gmail.com").first()
if not superadmin:
    new_superadmin = User(
        id=str(uuid.uuid4()),
        email="abhi2602k@gmail.com",
        name="Super Admin",
        hashed_password=get_password_hash("Aashu@123"),
        role=RoleEnum.SUPERADMIN
    )
    db.add(new_superadmin)
    db.commit()
    print("Superadmin created successfully!")
else:
    # Update just in case
    superadmin.role = RoleEnum.SUPERADMIN
    superadmin.hashed_password = get_password_hash("Aashu@123")
    db.commit()
    print("Superadmin updated successfully!")

db.close()
