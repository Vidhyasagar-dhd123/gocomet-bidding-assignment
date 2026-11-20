from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "RFQ British Auction API"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://bidding:bidding@localhost:5434/bidding" # bidding for just now
    redis_url: str = "redis://localhost:6380/0"
    sql_echo: bool = False

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"] # I can use vite / react

    enable_closer: bool = True
    closer_interval_seconds: float = 2.0

    sse_heartbeat_seconds: float = 15.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
