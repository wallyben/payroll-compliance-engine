from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from apps.api.db import get_db
from apps.api import models
from apps.api.schemas import LoginIn, TokenOut
from apps.api.security import verify_password, create_access_token
from apps.api.deps import require_role

router = APIRouter()

@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(sub=user.email, role=user.role)
    return TokenOut(access_token=token)

@router.get("/me")
def me(user=Depends(require_role("admin","auditor","viewer"))):
    return user
