import sys
from sqlalchemy.orm import Session
from apps.api.db import SessionLocal, Base, engine
from apps.api.models import User
from apps.api.security import hash_password

def main(email: str, password: str):
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email.lower()).first()
        if existing:
            print("User exists")
            return
        u = User(email=email.lower(), password_hash=hash_password(password), role="admin")
        db.add(u); db.commit()
        print("Created admin:", email)
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: seed_admin.py <email> <password>")
        raise SystemExit(2)
    main(sys.argv[1], sys.argv[2])
