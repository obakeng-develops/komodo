import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from sqlalchemy import text

from app.config import get_settings
from app.database import Base, engine
from app.idempotency import idempotency_middleware
from app.routers import (
    agent,
    auth,
    fleet,
    guardrails,
    hosts,
    incidents,
    learnings,
    me,
    services,
    settings,
    stream,
    users,
)
from app.config import get_settings

if get_settings().allow_simulate:
    from app.routers import simulate

from app.monitor import monitor
from app.seed import ensure_seed_data


DEFAULT_AUTH_SECRET = "dev-insecure-change-me"


def _configure_logging() -> None:
    """Send the app's own `oncall.*` logs (and the #54 wide events) to stdout at
    INFO. uvicorn configures only its own loggers and leaves the root logger
    without an INFO handler, so without this every oncall INFO line — including
    every wide event — is silently dropped in production. Scoped to `oncall` so
    uvicorn's access logs are untouched; propagate=False avoids double-logging.
    """
    oncall = logging.getLogger("oncall")
    if oncall.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    oncall.addHandler(handler)
    oncall.setLevel(logging.INFO)
    oncall.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    # Fail closed: the session JWT is signed with AUTH_SECRET. If it is still the
    # built-in default, anyone could forge an owner session. Refuse to serve.
    if get_settings().auth_secret == DEFAULT_AUTH_SECRET:
        raise RuntimeError(
            "AUTH_SECRET is unset (still the built-in default). "
            "Set a strong, random AUTH_SECRET before starting Komodo."
        )
    Base.metadata.create_all(bind=engine)
    # create_all adds new tables but never alters existing ones. On Postgres
    # (production), patch in columns introduced after a table's first deploy,
    # idempotently. SQLite (local dev) has no "ADD COLUMN IF NOT EXISTS" syntax
    # and gets every column from create_all on a fresh file, so skip it there.
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE hosts ADD COLUMN IF NOT EXISTS autonomy VARCHAR"))
            conn.execute(text("ALTER TABLE hosts ADD COLUMN IF NOT EXISTS agent_version VARCHAR"))
            conn.execute(text("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS fly_api_token_encrypted VARCHAR"))
            conn.execute(text("ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS fly_apps JSON"))
            conn.execute(text("ALTER TABLE services ADD COLUMN IF NOT EXISTS fly_app VARCHAR"))
    ensure_seed_data()
    await monitor.start()
    yield
    await monitor.stop()


app = FastAPI(title="Komodo API", version="1.0.0", lifespan=lifespan)

app_settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(idempotency_middleware)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(me.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(hosts.router, prefix="/api/v1")
app.include_router(services.router, prefix="/api/v1")
app.include_router(fleet.router, prefix="/api/v1")
app.include_router(incidents.router, prefix="/api/v1")
app.include_router(learnings.router, prefix="/api/v1")
app.include_router(guardrails.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
if get_settings().allow_simulate:
    app.include_router(simulate.router, prefix="/api/v1")
app.include_router(stream.router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}


# Serve the built SvelteKit SPA (single origin with the API). Present only in the
# combined image / production build; in local dev the frontend runs under Vite.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if (STATIC_DIR / "index.html").exists():

    @app.get("/{path:path}")
    async def spa(path: str):
        # /api/* and /health are matched above; keep unknown API paths as JSON 404s.
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = STATIC_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
