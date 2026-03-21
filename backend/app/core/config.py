"""Application configuration with environment variable support."""

from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    # Application
    APP_NAME: str = "Workflow Engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://workflow:workflow@localhost:5432/workflow_engine"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Security
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ENCRYPTION_KEY: str = ""  # Fernet key for variable encryption
    API_KEY_HEADER: str = "X-API-Key"
    WEBHOOK_SECRET: str = "webhook-secret-change-me"

    # Celery
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3600
    CELERY_TASK_TIME_LIMIT: int = 7200
    CELERY_WORKER_CONCURRENCY: int = 4

    # Scheduler
    SCHEDULER_POLL_INTERVAL: int = 10  # seconds
    DEFAULT_MAX_RETRIES: int = 3
    DEFAULT_RETRY_DELAY: int = 60  # seconds

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": True}


@lru_cache
def get_settings() -> Settings:
    return Settings()
