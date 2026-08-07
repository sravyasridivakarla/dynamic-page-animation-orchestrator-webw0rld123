"""Page Config Drafter configuration."""

import os


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Page Config Drafter")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@db:5432/backend",
    )
    KG_SERVICE_URL: str = os.getenv("KG_SERVICE_URL", "http://kg-service:8001")
    PROVENANCE_URL: str = os.getenv("PROVENANCE_URL", "http://provenance-service:8002")
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]


settings = Settings()
