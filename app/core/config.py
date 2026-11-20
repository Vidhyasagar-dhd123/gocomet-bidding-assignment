import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "RFQ British Auction API"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://bidding:bidding@localhost:5434/bidding"
    redis_url: str = "redis://localhost:6380/0"
    sql_echo: bool = False

    cors_origins: list[str] | str = ["http://localhost:5173", "http://localhost:3000"]

    enable_closer: bool = True
    closer_interval_seconds: float = 2.0

    sse_heartbeat_seconds: float = 15.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            value = value.strip()
            if value.startswith("[") and value.endswith("]"):
                try:
                    return json.loads(value)
                except Exception:
                    pass
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, (list, tuple)):
            return [str(v).strip() for v in value]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
