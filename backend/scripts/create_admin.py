"""
Create the first administrator account.

Usage (from backend/ directory):
    python scripts/create_admin.py

Credentials are read from environment variables (or .env):
    ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.config import get_settings
from app.database import SyncSessionLocal
from app.models.user import User, UserRole
from app.services.auth_service import hash_password

# For SQLite: ensure tables exist before inserting
settings = get_settings()
if "sqlite" in settings.sync_database_url:
    from sqlalchemy import create_engine
    from app.database import Base
    import app.models  # noqa
    engine = create_engine(settings.sync_database_url)
    Base.metadata.create_all(engine)


def create_admin() -> None:
    email = settings.admin_email.lower()
    password = settings.admin_password
    name = settings.admin_name

    if not email or not password or password == "ChangeMe123!":
        print(
            "ERROR: Set ADMIN_EMAIL, ADMIN_PASSWORD, and ADMIN_NAME in .env\n"
            "       Default password 'ChangeMe123!' is not accepted."
        )
        sys.exit(1)

    from sqlalchemy.orm import Session
    db: Session = SyncSessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.role == UserRole.admin:
                print(f"Admin already exists: {email}")
            else:
                print(f"ERROR: {email} exists as a student account.")
                sys.exit(1)
            return

        admin = User(
            email=email,
            name=name,
            hashed_password=hash_password(password),
            role=UserRole.admin,
            is_active=True,
        )
        db.add(admin)
        db.commit()
        print(f"✓ Administrator created: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
