from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import crypto
from app.deps import get_current_user, get_db_session, require_owner
from app.models import User, UserSettings
from app.schemas import UserSettingsOut, UserSettingsUpdate

router = APIRouter(prefix="/me/settings", tags=["settings"])


def _settings_out(settings: UserSettings) -> UserSettingsOut:
    decrypted = crypto.decrypt(settings.llm_api_key_encrypted)
    data = {
        "id": settings.id,
        "autonomy": settings.autonomy,
        "ask_below_pct": settings.ask_below_pct,
        "quiet_low_severity": settings.quiet_low_severity,
        "escalation_contact": settings.escalation_contact,
        "phone_number": settings.phone_number,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_api_key": crypto.mask_key(decrypted),
    }
    return UserSettingsOut(**data)


@router.get("", response_model=UserSettingsOut)
def read_settings(user: User = Depends(get_current_user)):
    return _settings_out(user.settings)


@router.patch("", response_model=UserSettingsOut)
def update_settings(
    update: UserSettingsUpdate,
    db: Session = Depends(get_db_session),
    user: User = Depends(get_current_user),
    _owner: User = Depends(require_owner),
):
    settings = db.query(UserSettings).filter(UserSettings.user_id == user.id).first()
    if not settings:
        settings = UserSettings(user_id=user.id)
        db.add(settings)

    data = update.model_dump(exclude_unset=True)
    if "llm_api_key" in data:
        data["llm_api_key_encrypted"] = crypto.encrypt(data.pop("llm_api_key"))

    for key, value in data.items():
        setattr(settings, key, value)

    db.commit()
    db.refresh(settings)
    return _settings_out(settings)
