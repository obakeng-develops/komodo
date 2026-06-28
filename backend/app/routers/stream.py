import asyncio
import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from app.deps import allowed_host_ids, current_identity
from app.models import User
from app.monitor import monitor
from app.stream import stream_manager

router = APIRouter(prefix="/stream", tags=["stream"])


def _hide_incident(data: dict) -> dict:
    """A resting state with no incident — what a restricted operator sees when
    the active incident is on a server they can't access. See issue #30."""
    return {
        **data,
        "incident_id": None, "service_id": None, "service_name": None, "host_id": None,
        "view": "resting", "can_approve": False, "can_take_over": False, "can_hand_back": False,
        "timeline": [], "proposed_fix": None,
        "llm_diagnosis": None, "llm_suggested_fix": None, "llm_confidence": None,
        "status_text": "all green", "status_dot": "green",
    }


@router.get("")
def stream(
    user: User = Depends(current_identity),
    allowed: set[str] | None = Depends(allowed_host_ids),
):
    queue = stream_manager.connect()

    def visible(event: str, data: dict):
        """Filter an event for this viewer. Returns the (possibly altered) data,
        or None to drop it. Unrestricted viewers see everything."""
        if allowed is None:
            return data
        if event == "incident_state":
            return data if data.get("host_id") in allowed else _hide_incident(data)
        if event == "log_lines":
            # Live logs of the active incident — withhold if it's not their server.
            return data if data.get("host_id") in allowed else None
        return data

    async def event_generator():
        try:
            state = monitor.get_state().model_dump()
            state = visible("incident_state", state)
            yield {"event": "incident_state", "data": json.dumps(state)}

            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    data = visible(message["event"], message["data"])
                    if data is None:
                        continue
                    yield {"event": message["event"], "data": json.dumps(data)}
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": json.dumps({"time": str(asyncio.get_event_loop().time())})}
        finally:
            stream_manager.disconnect(queue)

    return EventSourceResponse(event_generator())
