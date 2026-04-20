from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "FinKernel"
    environment: Literal["development", "test", "production"] = "development"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://finkernel:change-me@localhost:5432/finkernel"
    redis_url: str | None = "redis://localhost:6379/0"
    enable_pgvector: bool = True

    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_base_url: str = "https://data.alpaca.markets"
    alpaca_api_key: str | None = None
    alpaca_secret_key: str | None = None

    discord_bot_token: str | None = None
    discord_channel_id: int | None = None
    discord_command_prefix: str = "!"
    discord_allowed_user_ids_csv: str = ""

    allowed_symbols_csv: str = "AAPL,MSFT,GOOGL,AMZN,NVDA,META,TSLA"
    max_limit_order_qty: int = 100
    max_limit_order_notional: float = 10000.0
    default_time_in_force: str = "day"
    reconciliation_interval_seconds: int = 60
    advisor_loop_interval_seconds: int = 300
    profile_store_path: str = "config/persona-profiles.json"
    default_profile_account_id: str = "paper-account-1"
    @property
    def allowed_symbols(self) -> set[str]:
        return {symbol.strip().upper() for symbol in self.allowed_symbols_csv.split(",") if symbol.strip()}

    @property
    def discord_allowed_user_ids(self) -> set[str]:
        return {user_id.strip() for user_id in self.discord_allowed_user_ids_csv.split(",") if user_id.strip()}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
