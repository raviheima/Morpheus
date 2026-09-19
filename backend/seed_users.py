#!/usr/bin/env python3
"""
Seed the three default Morpheus accounts.

    python seed_users.py
"""

from app.database import Base, engine, SessionLocal
from app.auth.models import User
from app.auth.security import get_password_hash


DEFAULT_USERS = [
    ("admin",    "admin@morpheus.local",    "admin123", "admin"),
    ("examiner", "examiner@morpheus.local", "exam123",  "examiner"),
    ("viewer",   "viewer@morpheus.local",   "view123",  "viewer"),
]


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for username, email, password, role in DEFAULT_USERS:
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                existing.hashed_password = get_password_hash(password)
                existing.role = role
                existing.email = email
                existing.is_active = True
                print(f"  updated  {username} / {password}  ({role})")
            else:
                user = User(
                    username=username,
                    email=email,
                    hashed_password=get_password_hash(password),
                    role=role,
                    is_active=True,
                )
                db.add(user)
                print(f"  created  {username} / {password}  ({role})")
        db.commit()
        print("\nDone. Accounts:")
        print("  admin    / admin123   (admin)")
        print("  examiner / exam123    (examiner)")
        print("  viewer   / view123    (viewer)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
