from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_db_session, hash_password, require_owner
from app.models import Host, HostAccess, User
from app.schemas import ServerAccessUpdate, TeamMemberCreate, TeamMemberOut

router = APIRouter(prefix="/users", tags=["team"])


@router.get("", response_model=list[TeamMemberOut])
def list_team(
    db: Session = Depends(get_db_session),
    _owner: User = Depends(require_owner),
):
    return db.query(User).order_by(User.created_at).all()


@router.post("", response_model=TeamMemberOut, status_code=201)
def add_member(
    body: TeamMemberCreate,
    db: Session = Depends(get_db_session),
    _owner: User = Depends(require_owner),
):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=409, detail="A user with that email already exists")
    member = User(
        email=body.email,
        name=body.name,
        role="operator",
        password_hash=hash_password(body.password),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/{user_id}/servers", response_model=list[str])
def get_member_servers(
    user_id: str,
    db: Session = Depends(get_db_session),
    _owner: User = Depends(require_owner),
):
    member = db.query(User).filter(User.id == user_id).first()
    if not member or member.role == "owner":
        raise HTTPException(status_code=404, detail="Operator not found")
    return [r.host_id for r in db.query(HostAccess).filter(HostAccess.user_id == user_id).all()]


@router.put("/{user_id}/servers", response_model=list[str])
def set_member_servers(
    user_id: str,
    body: ServerAccessUpdate,
    db: Session = Depends(get_db_session),
    owner: User = Depends(require_owner),
):
    member = db.query(User).filter(User.id == user_id).first()
    if not member or member.role == "owner":
        raise HTTPException(status_code=404, detail="Operator not found")
    # Keep only host ids that are actually this fleet's servers.
    valid = {h.id for h in db.query(Host).filter(Host.user_id == owner.id).all()}
    ids = [hid for hid in dict.fromkeys(body.host_ids) if hid in valid]
    db.query(HostAccess).filter(HostAccess.user_id == user_id).delete()
    for hid in ids:
        db.add(HostAccess(user_id=user_id, host_id=hid))
    db.commit()
    return ids


@router.delete("/{user_id}", status_code=204)
def remove_member(
    user_id: str,
    db: Session = Depends(get_db_session),
    _owner: User = Depends(require_owner),
):
    member = db.query(User).filter(User.id == user_id).first()
    if not member:
        raise HTTPException(status_code=404, detail="User not found")
    if member.role == "owner":
        raise HTTPException(status_code=400, detail="Cannot remove the fleet owner")
    db.delete(member)
    db.commit()
    return None
