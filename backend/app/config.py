from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://komodo:komodo@localhost:5432/komodo"
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:4173"]
    url_poll_seconds: int = 30
    docker_verify_timeout_seconds: int = 90
    encryption_key: str | None = None
    allow_simulate: bool = False
    llm_service_url: str | None = None
    internal_api_key: str | None = None
    executor_signing_key: str | None = None  # PEM RSA private key
    executor_signing_key_file: str | None = None  # ...or read it from this path
    # user auth (JWT cookie sessions)
    auth_secret: str = "dev-insecure-change-me"
    owner_email: str | None = None
    owner_password: str | None = None
    cookie_secure: bool = False
    setup_token: str | None = None

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.executor_signing_key_file and not settings.executor_signing_key:
        settings.executor_signing_key = Path(settings.executor_signing_key_file).read_text()
    return settings
