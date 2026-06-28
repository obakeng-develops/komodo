from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db_session, require_owner
from app.models import Service, User
from app.schemas import ServiceCreate, ServiceOut, ServiceUpdate

router = APIRouter(prefix="/services", tags=["services"])


def _service_out(service: Service) -> ServiceOut:
    return ServiceOut(
        id=service.id,
        user_id=service.user_id,
        host_id=service.host_id,
        host_name=service.host.name if service.host else None,
        name=service.name,
        method=service.method,
        health_check_url=service.health_check_url,
        agent_token=service.agent_token,
        agent_host_info=service.agent_host_info,
        watch_logs=service.watch_logs,
        allowed_fix_action=service.allowed_fix_action,
        watch_only=service.watch_only,
        status=service.status,
        last_check_at=service.last_check_at,
        created_at=service.created_at,
    )


@router.get("", response_model=list[ServiceOut])
def list_services(user: User = Depends(get_current_user)):
    return [_service_out(s) for s in user.services]


@router.post("", response_model=ServiceOut, status_code=201)
def create_service(
    body: ServiceCreate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _owner: User = Depends(require_owner),
):
    if body.method != "url":
        raise HTTPException(status_code=400, detail="Only 'url' services can be created manually")
    service = Service(
        user_id=user.id,
        name=body.name,
        method="url",
        health_check_url=body.health_check_url,
        status="healthy",
        allowed_fix_action=None,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return _service_out(service)


@router.patch("/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: str,
    update: ServiceUpdate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _owner: User = Depends(require_owner),
):
    service = db.query(Service).filter(Service.id == service_id, Service.user_id == user.id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(service, key, value)
    db.commit()
    db.refresh(service)
    return _service_out(service)


@router.delete("/{service_id}", status_code=204)
def delete_service(
    service_id: str,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _owner: User = Depends(require_owner),
):
    service = db.query(Service).filter(Service.id == service_id, Service.user_id == user.id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    db.delete(service)
    db.commit()
    return None
