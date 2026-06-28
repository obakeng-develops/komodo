from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.config import get_settings
from app.database import Base, engine
from app.idempotency import idempotency_middleware
from app.routers import (
    agent,
    auth,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail closed: the session JWT is signed with AUTH_SECRET. If it is still the
    # built-in default, anyone could forge an owner session. Refuse to serve.
    if get_settings().auth_secret == DEFAULT_AUTH_SECRET:
        raise RuntimeError(
            "AUTH_SECRET is unset (still the built-in default). "
            "Set a strong, random AUTH_SECRET before starting Komodo."
        )
    Base.metadata.create_all(bind=engine)
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
