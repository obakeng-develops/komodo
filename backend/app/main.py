from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


@asynccontextmanager
async def lifespan(app: FastAPI):
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
