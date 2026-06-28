from fastapi import Depends, HTTPException, Header, Request
import hmac

import bcrypt
import jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Host, User

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


def _constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def verify_agent_token(token: str, token_hash: str | None) -> bool:
    if not token or not token_hash:
        return False
    # token_hash is stored as a bcrypt-style hash produced by hash_agent_token.
    # For the initial migration, plaintext tokens still compare directly.
    if token_hash.startswith("$2"):
        import bcrypt
        return bcrypt.checkpw(token.encode(), token_hash.encode())
    return _constant_time_compare(token, token_hash)


def hash_agent_token(token: str) -> str:
    import bcrypt
    return bcrypt.hashpw(token.encode(), bcrypt.gensalt()).decode()


def get_current_host(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Host:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[7:]
    host = db.query(Host).filter(Host.token == token).first()
    if host:
        return host
    # Fall back to hashed token comparison.
    for host in db.query(Host).all():
        if verify_agent_token(token, host.token_hash):
            return host
    raise HTTPException(status_code=401, detail="Invalid agent token")
