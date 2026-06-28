from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db_session, hash_password, verify_password
from app.models import User
from app.schemas import LoginRequest, SetupRequest, SetupStatus, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "auth"
SESSION_DAYS = 7


def _issue_session(response: Response, user: User) -> None:
    settings = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    token = jwt.encode(
        {"sub": user.id, "role": user.role, "exp": exp},
        settings.auth_secret,
        algorithm="HS256",
    )
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=SESSION_DAYS * 86400,
        path="/",
    )


def _owner_exists(db: Session) -> bool:
    """An owner who can actually log in (has a password)."""
    return (
        db.query(User)
        .filter(User.role == "owner", User.password_hash.isnot(None))
        .first()
        is not None
    )


@router.get("/setup-status", response_model=SetupStatus)
def setup_status(db: Session = Depends(get_db_session)):
    return SetupStatus(
        needs_setup=not _owner_exists(db),
        token_required=bool(get_settings().setup_token),
    )


@router.post("/setup", response_model=UserOut)
def setup(body: SetupRequest, response: Response, db: Session = Depends(get_db_session)):
    # First-run only: once an owner can log in, this is closed forever.
    if _owner_exists(db):
        raise HTTPException(status_code=403, detail="Setup already completed")

    configured = get_settings().setup_token
    if configured and body.token != configured:
        raise HTTPException(status_code=403, detail="Invalid setup token")

    # Claim the seeded fleet user (it owns the default settings + guardrails) so the
    # new owner inherits them; fall back to creating a fresh row only if none exists.
    owner = (
        db.query(User).filter(User.role == "owner").first()
        or db.query(User).filter(User.email == body.email).first()
        or db.query(User).first()
    )
    if owner is None:
        owner = User(email=body.email, name=body.name)
        db.add(owner)
    owner.email = body.email
    owner.name = body.name
    owner.role = "owner"
    owner.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(owner)

    _issue_session(response, owner)
    return owner


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db_session)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    _issue_session(response, user)
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
