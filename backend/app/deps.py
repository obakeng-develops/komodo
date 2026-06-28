from fastapi import Depends, HTTPException, Header, Request

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Host, HostAccess, User

get_db_session = get_db


# ---- user passwords (mirror the agent-token bcrypt helpers below) ----------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password or not password_hash:
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# ---- user auth: JWT in an HttpOnly cookie ----------------------------------
def current_identity(request: Request, db: Session = Depends(get_db)) -> User:
    """The logged-in user (could be owner or operator). 401 if not authenticated."""
    token = request.cookies.get("auth")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_settings().auth_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


def fleet_owner(db: Session = Depends(get_db), _: User = Depends(current_identity)) -> User:
    """The single fleet owner. All fleet data scopes to this user regardless of who is logged in.

    Depends on current_identity so it transitively requires a valid login.
    """
    owner = db.query(User).filter(User.role == "owner").first()
    if not owner:
        raise HTTPException(status_code=500, detail="No fleet owner configured")
    return owner


def require_owner(identity: User = Depends(current_identity)) -> User:
    if identity.role != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    return identity


# Existing routers scope queries via `== user.id`; pointing get_current_user at
# the fleet owner keeps all that working and scopes everyone to the one fleet.
get_current_user = fleet_owner


def allowed_host_ids(
    identity: User = Depends(current_identity),
    db: Session = Depends(get_db),
) -> set[str] | None:
    """The set of host ids the logged-in user may see and act on. None means
    unrestricted: owners always, and operators with no grants (see issue #30)."""
    if identity.role == "owner":
        return None
    rows = db.query(HostAccess.host_id).filter(HostAccess.user_id == identity.id).all()
    ids = {r[0] for r in rows}
    return ids or None


def host_allowed(allowed: set[str] | None, host_id: str | None) -> bool:
    """Whether a host (or a service's host) is visible given an allowed set.
    Unrestricted sees everything; a restricted operator never sees hostless
    (URL) services."""
    if allowed is None:
        return True
    return host_id is not None and host_id in allowed


def verify_agent_token(token: str, token_hash: str | None) -> bool:
    # We only ever store a bcrypt hash of the agent token, never the token itself.
    if not token or not token_hash:
        return False
    return bcrypt.checkpw(token.encode(), token_hash.encode())


def hash_agent_token(token: str) -> str:
    return bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()


def get_current_host(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Host:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[7:]
    # Authenticate against the stored bcrypt hash only. The plaintext token is
    # shown once at creation and never persisted, so a database read leaks nothing.
    for host in db.query(Host).all():
        if verify_agent_token(token, host.token_hash):
            return host
    raise HTTPException(status_code=401, detail="Invalid agent token")
