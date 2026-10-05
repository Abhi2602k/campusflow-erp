import os
import sys

# 1. Run scaffold scripts
print("Running scaffolds...")
os.system(f"{sys.executable} scaffold.py")
os.system(f"{sys.executable} scaffold2.py")
os.system(f"{sys.executable} scaffold3.py")

# 2. Add openpyxl to requirements
print("Adding openpyxl...")
with open("requirements.txt", "a") as f:
    f.write("openpyxl==3.1.2\n")

# 3. Update alembic.ini
print("Updating alembic.ini...")
with open("alembic.ini", "r") as f:
    ini_data = f.read()
ini_data = ini_data.replace(
    "sqlalchemy.url = driver://user:pass@localhost/dbname",
    "sqlalchemy.url = postgresql://erp_user:erp_password@localhost:5432/attendance_erp"
)
with open("alembic.ini", "w") as f:
    f.write(ini_data)

# 4. Update alembic/env.py
print("Updating env.py...")
with open("alembic/env.py", "r") as f:
    env_data = f.read()

import_lines = "import sys\nimport os\nsys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))\nfrom app.models.models import Base\n"
env_data = env_data.replace("target_metadata = None", import_lines + "target_metadata = Base.metadata")

with open("alembic/env.py", "w") as f:
    f.write(env_data)

print("Fixes applied successfully.")
