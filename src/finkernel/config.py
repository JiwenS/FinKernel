from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FinKernel"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api"
    storage_backend: Literal["file", "database"] = "file"
    profile_data_dir: str = ".finkernel"
    database_url: str = "postgresql+psycopg://finkernel:change-me@localhost:5432/finkernel"
    enable_pgvector: bool = True
    profile_store_path: str = "config/persona-profiles.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
