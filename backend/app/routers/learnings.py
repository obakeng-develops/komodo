from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db_session
from app.models import Learning, User
from app.schemas import LearningOut

router = APIRouter(prefix="/learnings", tags=["learnings"])


@router.get("", response_model=list[LearningOut])
def list_learnings(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    learnings = db.query(Learning).filter(Learning.user_id == user.id).all()
    service_names = {s.id: s.name for s in user.services}
    out = []
    for l in learnings:
        item = LearningOut.model_validate(l)
        item.service_name = service_names.get(l.service_id) if l.service_id else None
        out.append(item)
    return out
