import asyncio
import logging
import re
from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.config import ROOT
from app.deps import get_current_host, get_db_session
from app.models import Host
from app.monitor import monitor
from app.schemas import AgentBeatPayload, AgentBeatResponse, AgentLogPayload
from app.stream import stream_manager

logger = logging.getLogger("oncall.agent")

router = APIRouter(prefix="/agent", tags=["agent"])

_AGENT_SCRIPT = ROOT.parent / "agent" / "komodo-agent.py"


@lru_cache(maxsize=1)
def current_agent_version() -> str | None:
    """The AGENT_VERSION of the script this server serves — the version a host
    should be running. Cached for the process; a new deploy restarts it."""
    try:
        m = re.search(r'AGENT_VERSION\s*=\s*"([^"]+)"', _AGENT_SCRIPT.read_text())
        return m.group(1) if m else None
    except OSError:
        return None


@router.post("/beat", response_model=AgentBeatResponse)
async def agent_beat(
    payload: AgentBeatPayload,
    db: Session = Depends(get_db_session),
    host: Host = Depends(get_current_host),
):
    restart_actions, fetch_logs = await monitor.handle_agent_beat(host, payload.containers)
    logs = {c["name"]: c.get("logs") for c in payload.containers if c.get("logs")}
    if logs:
        await asyncio.to_thread(monitor.store_agent_logs, host, logs)
    host.last_seen_at = datetime.utcnow()
    if payload.agent_version:
        host.agent_version = payload.agent_version
    db.add(host)
    db.commit()
    logger.info("host=%s beat received containers=%d restart_actions=%d", host.name, len(payload.containers), len(restart_actions))
    stream_manager.broadcast("services_changed", {})
    tail_logs, _ = monitor.should_tail_logs()
    return AgentBeatResponse(restart=restart_actions, fetch_logs=fetch_logs, tail_logs=tail_logs)


@router.post("/logs")
async def agent_logs(
    payload: AgentLogPayload,
    host: Host = Depends(get_current_host),
):
    if payload.lines:
        stream_manager.broadcast("log_lines", {"lines": payload.lines, "host_id": host.id})
    return {"ok": True}


@router.get("/script", response_class=PlainTextResponse)
def agent_script():
    # Public on purpose: the script is open source, and the host token (not this
    # endpoint) is what authorizes an agent's beats. This lets the install
    # one-liner run unauthenticated on a fresh host.
    path = ROOT.parent / "agent" / "komodo-agent.py"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Agent script not found")
    return PlainTextResponse(path.read_text(), media_type="text/x-python")
