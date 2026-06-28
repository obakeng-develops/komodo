from fastapi import APIRouter, Depends, HTTPException

from app.config import get_settings
from app.deps import require_owner
from app.models import User
from app.schemas import ActiveIncidentState
from app.monitor import monitor

router = APIRouter(prefix="/simulate", tags=["simulate"])


@router.post("", response_model=ActiveIncidentState)
async def simulate(
    user: User = Depends(require_owner),
):
    if not get_settings().allow_simulate:
        raise HTTPException(status_code=404, detail="Simulator disabled")
    return await monitor.simulate()
