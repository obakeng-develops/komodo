from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import current_identity, get_db_session
from app.models import User
from app.schemas import UserOut, UserUpdate

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserOut)
def read_me(user: User = Depends(current_identity)):
    return user


@router.patch("", response_model=UserOut)
def update_me(
    update: UserUpdate,
    db: Session = Depends(get_db_session),
    user: User = Depends(current_identity),
):
    for key, value in update.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user
