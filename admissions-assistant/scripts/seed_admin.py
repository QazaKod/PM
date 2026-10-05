"""Script to seed default admin user."""
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db_session import SessionLocal
from app.models import User
from app.security import hash_password


def seed_admin():
    db = SessionLocal()
    try:
        admin_email = "admin@sdu.edu.kz"
        admin_user = db.query(User).filter(User.email == admin_email).first()
        if not admin_user:
            admin_user = User(
                email=admin_email,
                hashed_password=hash_password("AdminPassword2026!"),
                full_name="Admissions Superadmin",
                role="admin",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print(f"Created default admin: {admin_email} / AdminPassword2026!")
        else:
            print(f"Admin already exists: {admin_email}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_admin()
