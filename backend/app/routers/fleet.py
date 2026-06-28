"""Fleet view: servers and their services with an uptime summary.

Part fleet inventory, part uptime monitor. Uptime is derived from incident
history over a window, not a separate pinger — an incident is a stretch where a
service wasn't healthy. See issue #24.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db_session
from app.models import Incident, Service, User

router = APIRouter(prefix="/fleet", tags=["fleet"])

_STATUS_ORDER = {"down": 0, "degraded": 1, "healthy": 2}


class FleetIncident(BaseModel):
    started_at: datetime
    resolved_at: datetime | None
    severity: str
    status: str


class FleetService(BaseModel):
    id: str
    name: str
    status: str
    watch_only: bool
    uptime_pct: float
    incidents: list[FleetIncident]  # within the window, most recent first


class FleetServer(BaseModel):
    name: str  # host name, or "URL checks" for services with no host
    down: int
    degraded: int
    services: list[FleetService]


class FleetOut(BaseModel):
    window_hours: int
    servers: list[FleetServer]


@router.get("", response_model=FleetOut)
def get_fleet(
    window_hours: int = Query(168, ge=1, le=720),
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    now = datetime.utcnow()
    window_start = now - timedelta(hours=window_hours)
    window_seconds = window_hours * 3600

    services = db.query(Service).filter(Service.user_id == user.id).all()
    incidents = (
        db.query(Incident)
        .filter(
            Incident.user_id == user.id,
            (Incident.resolved_at.is_(None)) | (Incident.resolved_at >= window_start),
        )
        .order_by(Incident.started_at.desc())
        .all()
    )
    by_service: dict[str, list[Incident]] = {}
    for inc in incidents:
        by_service.setdefault(inc.service_id, []).append(inc)

    groups: dict[str, list[FleetService]] = {}
    for s in services:
        downtime = 0.0
        out: list[FleetIncident] = []
        for inc in by_service.get(s.id, []):
            start = max(inc.started_at, window_start)
            end = inc.resolved_at or now
            if end > start:
                downtime += (end - start).total_seconds()
            out.append(FleetIncident(
                started_at=inc.started_at, resolved_at=inc.resolved_at,
                severity=inc.severity, status=inc.status,
            ))
        downtime = min(downtime, window_seconds)
        uptime_pct = round(100.0 * (1 - downtime / window_seconds), 3)
        server = s.host.name if s.host else "URL checks"
        groups.setdefault(server, []).append(FleetService(
            id=s.id, name=s.name, status=s.status, watch_only=s.watch_only,
            uptime_pct=uptime_pct, incidents=out[:10],
        ))

    servers: list[FleetServer] = []
    for name, svcs in groups.items():
        svcs.sort(key=lambda x: (_STATUS_ORDER.get(x.status, 3), x.name))
        servers.append(FleetServer(
            name=name,
            down=sum(1 for x in svcs if x.status == "down"),
            degraded=sum(1 for x in svcs if x.status == "degraded"),
            services=svcs,
        ))
    servers.sort(key=lambda g: (-g.down, -g.degraded, g.name))
    return FleetOut(window_hours=window_hours, servers=servers)
