from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    encryption_key: str | None = None
    internal_api_key: str | None = None
    host: str = "0.0.0.0"
    port: int = 8001
    default_provider: str = "deepseek"
    default_model: str = "deepseek-v4-pro"

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
