"""Page Config Drafter configuration."""

import os
from typing import List


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Page Config Drafter")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@db:5432/page_config_drafter",
    )
    KG_SERVICE_URL: str = os.getenv("KG_SERVICE_URL", "http://kg-service:8001")
    PROVENANCE_STORE_URL: str = os.getenv(
        "PROVENANCE_STORE_URL", "http://provenance-store:8002"
    )
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")


settings = Settings()
