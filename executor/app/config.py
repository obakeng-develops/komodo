from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    public_key: str | None = None  # PEM-formatted RSA public key
    public_key_file: str | None = None
    host: str = "0.0.0.0"
    port: int = 8002
    allow_simulate: bool = False

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.public_key_file and not settings.public_key:
        settings.public_key = Path(settings.public_key_file).read_text()
    return settings
