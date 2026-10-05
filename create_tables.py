import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import engine
from app.models.models import Base

print("Creating all missing tables...")
Base.metadata.create_all(bind=engine)
print("Done.")
