import sqlite3
import uuid
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.core.security import get_password_hash

def seed_custom_user():
    db_path = "attendance.db"
    
    if not os.path.exists(db_path):
        print("Database not found. Make sure migrations are applied.")
        return

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    email = "abhishek0157041@gmail.com"
    password = "Aashu@123"
    hashed = get_password_hash(password)
    user_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")

    try:
        c.execute('''INSERT INTO users (id, email, hashed_password, role, name, is_active, created_at, updated_at) 
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                  (user_id, email, hashed, 'ADMIN', 'Abhishek Admin', 1, now, now))
        conn.commit()
        print(f"Successfully created ADMIN user: {email} / {password}")
    except sqlite3.IntegrityError:
        print(f"User {email} already exists.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_custom_user()
