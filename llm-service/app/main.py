import hmac
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from app.config import get_settings
from app.llm import diagnose


def _configure_logging() -> None:
    """Send the service's `llm.*` logs to stdout at INFO. uvicorn leaves the root
    logger without an INFO handler, so otherwise the diagnosis reasons (no key,
    parse failure, upstream error) are silently dropped. See Komodo #61/#66."""
    llm = logging.getLogger("llm")
    if llm.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    llm.addHandler(handler)
    llm.setLevel(logging.INFO)
    llm.propagate = False


class DiagnoseRequest(BaseModel):
    context: dict
    api_key_encrypted: str | None = None
    provider: str | None = None
    model: str | None = None


class DiagnoseResponse(BaseModel):
    diagnosis: str | None = None
    suggested_fix: str | None = None
    confidence: str | None = None
    action: str | None = None  # restart_container | none — the server validates it


def _verify_internal_key(x_internal_api_key: str | None = Header(None)):
    expected = get_settings().internal_api_key
    if not expected:
        raise HTTPException(status_code=500, detail="INTERNAL_API_KEY not configured")
    if not (x_internal_api_key and hmac.compare_digest(x_internal_api_key, expected)):
        raise HTTPException(status_code=401, detail="Invalid internal API key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    yield


app = FastAPI(title="Komodo LLM Service", version="1.0.0", lifespan=lifespan)


@app.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose_endpoint(
    req: DiagnoseRequest,
    _=Depends(_verify_internal_key),
):
    result = await diagnose(
        req.context,
        api_key_encrypted=req.api_key_encrypted,
        provider=req.provider or get_settings().default_provider,
        model=req.model or get_settings().default_model,
    )
    if not result:
        return DiagnoseResponse()
    return DiagnoseResponse(**result)


@app.get("/health")
def health():
    return {"status": "ok"}
