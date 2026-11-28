from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "NORAM Attendance Platform"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str = (
        "postgresql+psycopg://attendance_user:attendance_dev_pass@localhost:5432/attendance_platform"
    )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        if cleaned.startswith("postgres://"):
            return "postgresql+psycopg://" + cleaned[len("postgres://") :]
        if cleaned.startswith("postgresql://"):
            return "postgresql+psycopg://" + cleaned[len("postgresql://") :]
        return cleaned

    SECRET_KEY: str = "dev-only-insecure-key-change-in-production-64-chars-minimum-123456"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    TERMINAL_RESET_DELAY_SECONDS: int = 4
    PIN_MAX_FAILED_ATTEMPTS: int = 5
    PIN_LOCKOUT_MINUTES: int = 15
    LOGIN_RATE_LIMIT_PER_MINUTE: int = 10

    BACKEND_CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:3001,https://staff-attendance-brown.vercel.app"
    )
    BACKEND_CORS_ORIGIN_REGEX: Optional[str] = r"^https://.*\.vercel\.app$"

    SEED_DEMO_DATA: bool = False
    PLATFORM_ADMIN_EMAIL: str = "platform-admin@noramdigital.com"
    PLATFORM_ADMIN_PASSWORD: str = "ChangeMeDevAdmin!2026"

    @property
    def cors_origins_list(self) -> List[str]:
        return [
            origin.strip()
            for origin in self.BACKEND_CORS_ORIGINS.split(",")
            if origin.strip()
        ]


settings = Settings()
