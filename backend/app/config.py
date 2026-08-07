"""Page Config Drafter configuration."""

import os


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "Page Config Drafter")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/backend",
    )
    KG_SERVICE_URL: str = os.getenv("KG_SERVICE_URL", "http://localhost:8001")
    PROVENANCE_URL: str = os.getenv("PROVENANCE_URL", "http://localhost:8002")
    CORS_ORIGINS: list = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
    ).split(",")

    def validate(self) -> None:
        required = ["DATABASE_URL", "KG_SERVICE_URL", "PROVENANCE_URL"]
        missing = [k for k in required if not getattr(self, k, None)]
        if missing:
            raise RuntimeError(f"Missing required configuration: {', '.join(missing)}")


settings = Settings()
