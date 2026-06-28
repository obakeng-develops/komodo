import json
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from app.auth import validate_action_token, verify_internal_state
from app.config import get_settings
from app.dockerctl import list_containers, restart, start, stop, logs


class ExecuteRequest(BaseModel):
    action_token: str
    internal_state: str | None = None


class ExecuteResponse(BaseModel):
    ok: bool
    output: str | None = None


class StatusResponse(BaseModel):
    containers: list[dict]


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Komodo Executor", version="1.0.0", lifespan=lifespan)


async def _run_action(payload: dict) -> tuple[bool, str | None]:
    action = payload.get("action")
    container = payload.get("container")
    if action == "list_containers":
        cs = await list_containers()
        return True, json.dumps(cs)
    if action in ("restart_container", "stop_container", "start_container", "fetch_logs") and not container:
        return False, "container required"
    if action == "restart_container":
        return await restart(container), None
    if action == "start_container":
        return await start(container), None
    if action == "stop_container":
        if not get_settings().allow_simulate:
            return False, "simulate disabled"
        return await stop(container), None
    if action == "fetch_logs":
        tail = payload.get("tail", 50)
        out = await logs(container, tail=tail)
        return out is not None, out
    return False, "unknown action"


@app.post("/execute", response_model=ExecuteResponse)
async def execute(req: ExecuteRequest):
    payload = validate_action_token(req.action_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid action token")
    if req.internal_state and not await verify_internal_state(req.internal_state):
        raise HTTPException(status_code=401, detail="Invalid internal state")
    ok, output = await _run_action(payload)
    return ExecuteResponse(ok=ok, output=output)


@app.get("/status", response_model=StatusResponse)
async def status():
    return StatusResponse(containers=await list_containers())


@app.get("/health")
def health():
    return {"status": "ok"}
