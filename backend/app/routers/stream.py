import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.deps import current_identity
from app.models import User
from app.monitor import monitor
from app.stream import stream_manager

router = APIRouter(prefix="/stream", tags=["stream"])


@router.get("")
def stream(user: User = Depends(current_identity)):
    queue = stream_manager.connect()

    async def event_generator():
        try:
            # Send current state immediately
            state = monitor.get_state()
            yield {
                "event": "incident_state",
                "data": json.dumps(state.model_dump()),
            }

            while True:
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30)
                    yield {
                        "event": message["event"],
                        "data": json.dumps(message["data"]),
                    }
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": json.dumps({"time": str(asyncio.get_event_loop().time())})}
        finally:
            stream_manager.disconnect(queue)

    return EventSourceResponse(event_generator())
