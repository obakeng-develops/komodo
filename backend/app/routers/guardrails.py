from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db_session, require_owner
from app.models import Guardrail, User
from app.schemas import GuardrailOut, GuardrailUpdate

router = APIRouter(prefix="/guardrails", tags=["guardrails"])


def _to_out(guardrail: Guardrail, service_names: dict[str, str]) -> GuardrailOut:
    out = GuardrailOut.model_validate(guardrail)
    out.service_name = service_names.get(guardrail.service_id) if guardrail.service_id else None
    return out


@router.get("", response_model=list[GuardrailOut])
def list_guardrails(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    service_names = {s.id: s.name for s in user.services}
    guardrails = db.query(Guardrail).filter(Guardrail.user_id == user.id).all()
    return [_to_out(g, service_names) for g in guardrails]


@router.patch("/{key}", response_model=GuardrailOut)
def update_guardrail(
    key: str,
    update: GuardrailUpdate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _owner: User = Depends(require_owner),
):
    guardrail = (
        db.query(Guardrail).filter(Guardrail.key == key, Guardrail.user_id == user.id).first()
    )
    if not guardrail:
        raise HTTPException(status_code=404, detail="Guardrail not found")
    if guardrail.kind == "locked":
        raise HTTPException(status_code=400, detail="Cannot modify a locked guardrail")
    guardrail.value = update.value
    db.commit()
    db.refresh(guardrail)
    service_names = {s.id: s.name for s in user.services}
    return _to_out(guardrail, service_names)
