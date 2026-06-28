from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.deps import allowed_host_ids, current_identity, get_current_user, host_allowed
from app.database import get_db
from app.models import Incident, IncidentEvent, Service, User
from app.pagination import paginate
from app.schemas import (
    CursorParams,
    IncidentEventOut,
    IncidentListItem,
    IncidentOut,
    PaginatedIncidents,
)
from app.monitor import monitor

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _require_active_incident(incident_id: str):
    active_id = monitor.get_state().incident_id
    if active_id != incident_id:
        raise HTTPException(status_code=409, detail="Incident is not the active incident")


def _authorize_host(incident_id: str, db: Session, allowed: set[str] | None):
    """403 if the caller's server access doesn't cover this incident's host."""
    if allowed is None:
        return
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    host_id = inc.service.host_id if inc and inc.service else None
    if not host_allowed(allowed, host_id):
        raise HTTPException(status_code=403, detail="Not permitted for this server")


@router.get("", response_model=PaginatedIncidents)
def list_incidents(
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    allowed: set[str] | None = Depends(allowed_host_ids),
):
    params = CursorParams(cursor=cursor, limit=limit)
    query = db.query(Incident).filter(Incident.user_id == user.id)
    if allowed is not None:
        query = query.join(Service, Incident.service_id == Service.id).filter(
            Service.host_id.in_(allowed)
        )
    items, next_cursor, has_more = paginate(
        db,
        query,
        cursor=params.cursor,
        limit=params.limit,
        sort_column=Incident.started_at,
        sort_asc=False,
    )

    service_names = {s.id: s.name for s in user.services}
    data = []
    for inc in items:
        item = IncidentListItem.model_validate(inc)
        item.service_name = service_names.get(inc.service_id)
        data.append(item)

    return PaginatedIncidents(data=data, next_cursor=next_cursor, has_more=has_more)


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(
    incident_id: str,
    include: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    allowed: set[str] | None = Depends(allowed_host_ids),
):
    incident = (
        db.query(Incident).filter(Incident.id == incident_id, Incident.user_id == user.id).first()
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not host_allowed(allowed, incident.service.host_id if incident.service else None):
        raise HTTPException(status_code=404, detail="Incident not found")

    service_names = {s.id: s.name for s in user.services}
    out = IncidentOut.model_validate(incident)
    out.service_name = service_names.get(incident.service_id)
    if include and "events" in include:
        out.events = [IncidentEventOut.model_validate(e) for e in incident.events]
    return out


@router.get("/{incident_id}/events", response_model=list[IncidentEventOut])
def list_incident_events(
    incident_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    allowed: set[str] | None = Depends(allowed_host_ids),
):
    incident = (
        db.query(Incident).filter(Incident.id == incident_id, Incident.user_id == user.id).first()
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not host_allowed(allowed, incident.service.host_id if incident.service else None):
        raise HTTPException(status_code=404, detail="Incident not found")
    return [IncidentEventOut.model_validate(e) for e in incident.events]


@router.post("/{incident_id}/approve")
async def approve_incident(
    incident_id: str,
    user: User = Depends(current_identity),
    db: Session = Depends(get_db),
    allowed: set[str] | None = Depends(allowed_host_ids),
):
    _require_active_incident(incident_id)
    _authorize_host(incident_id, db, allowed)
    state = await monitor.approve()
    return state


@router.post("/{incident_id}/take-over")
async def take_over_incident(
    incident_id: str,
    user: User = Depends(current_identity),
    db: Session = Depends(get_db),
    allowed: set[str] | None = Depends(allowed_host_ids),
):
    _require_active_incident(incident_id)
    _authorize_host(incident_id, db, allowed)
    state = await monitor.take_over()
    return state


@router.post("/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    user: User = Depends(current_identity),
    db: Session = Depends(get_db),
    allowed: set[str] | None = Depends(allowed_host_ids),
):
    _require_active_incident(incident_id)
    _authorize_host(incident_id, db, allowed)
    state = await monitor.resolve(manual=True)
    return state


@router.post("/{incident_id}/hand-back")
async def hand_back_incident(
    incident_id: str,
    user: User = Depends(current_identity),
    db: Session = Depends(get_db),
    allowed: set[str] | None = Depends(allowed_host_ids),
):
    _require_active_incident(incident_id)
    _authorize_host(incident_id, db, allowed)
    state = await monitor.hand_back()
    return state
