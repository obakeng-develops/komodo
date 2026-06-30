import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ConfigDict
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db_session, hash_agent_token, require_owner
from app.models import Host, User
from app.routers.agent import current_agent_version
from app.schemas import HostCreate, HostOut, HostUpdate
from app.stream import stream_manager
from pydantic import BaseModel
from datetime import datetime

class HostOutWithToken(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    token: str
    token_preview: str
    last_seen_at: datetime | None = None
    created_at: datetime


router = APIRouter(prefix="/hosts", tags=["hosts"])


def _token_preview(token: str) -> str:
    return f"{token[:6]}...{token[-6:]}"


def _host_out(host: Host) -> HostOut:
    current = current_agent_version()
    # Flag a host whose agent has reported but isn't on the served version. A
    # never-seen host (no agent yet) and an unknown server version are not flagged.
    outdated = bool(host.last_seen_at and current and host.agent_version != current)
    return HostOut(
        id=host.id,
        name=host.name,
        token_preview=_token_preview(host.token_hash or host.token or ""),
        last_seen_at=host.last_seen_at,
        created_at=host.created_at,
        autonomy=host.autonomy,
        agent_version=host.agent_version,
        agent_outdated=outdated,
    )


@router.get("", response_model=list[HostOut])
def list_hosts(user: User = Depends(get_current_user)):
    return [_host_out(h) for h in user.hosts]


@router.post("", response_model=HostOutWithToken, status_code=201)
def create_host(
    body: HostCreate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _owner: User = Depends(require_owner),
):
    existing = db.query(Host).filter(Host.user_id == user.id, Host.name == body.name).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"A server named '{body.name}' already exists.",
        )
    token = secrets.token_urlsafe(32)
    # Persist only the bcrypt hash; the raw token is returned once, never stored.
    host = Host(
        user_id=user.id,
        name=body.name,
        token_hash=hash_agent_token(token),
    )
    db.add(host)
    db.commit()
    db.refresh(host)
    return HostOutWithToken(
        id=host.id,
        name=host.name,
        token=token,
        token_preview=_token_preview(token),
        last_seen_at=host.last_seen_at,
        created_at=host.created_at,
    )


@router.patch("/{host_id}", response_model=HostOut)
def update_host(
    host_id: str,
    body: HostUpdate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _owner: User = Depends(require_owner),
):
    if body.autonomy not in (None, "auto_fix", "ask_first"):
        raise HTTPException(status_code=422, detail="autonomy must be auto_fix, ask_first, or null")
    host = db.query(Host).filter(Host.id == host_id, Host.user_id == user.id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    host.autonomy = body.autonomy
    db.add(host)
    db.commit()
    db.refresh(host)
    return _host_out(host)


@router.delete("/{host_id}", status_code=204)
def delete_host(
    host_id: str,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _owner: User = Depends(require_owner),
):
    host = db.query(Host).filter(Host.id == host_id, Host.user_id == user.id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    # ORM-delete each service (not a bulk delete) so the cascades fire and take
    # the services' incidents, learnings, and guardrails with them.
    for service in list(host.services):
        db.delete(service)
    db.delete(host)
    db.commit()
    # Removing a host drops its services; tell clients to refresh so the UI
    # stops "watching" a server that's gone. See #74.
    stream_manager.broadcast("services_changed", {})
    return None


@router.post("/{host_id}/rotate-token", response_model=HostOut)
def rotate_host_token(
    host_id: str,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _owner: User = Depends(require_owner),
):
    host = db.query(Host).filter(Host.id == host_id, Host.user_id == user.id).first()
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    token = secrets.token_urlsafe(32)
    host.token = None  # clear any legacy plaintext; we keep only the hash
    host.token_hash = hash_agent_token(token)
    db.commit()
    db.refresh(host)
    # ponytail: return full token on rotation so the user can update the agent.
    out = _host_out(host)
    out.token = token
    return out

