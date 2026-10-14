"""Settings: production refuses to boot without explicit secrets and a persistent DB."""
import secrets
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "RegTech Carbon Workspace"
    environment: str = "development"
    secret_key: str = ""
    db_url: str = "sqlite+aiosqlite:///./esg_platform.db"
    cors_origins: str = "http://localhost:3000"
    max_upload_size: int = 8 * 1024 * 1024
    factor_path: str = ""
    access_token_minutes: int = 60

    model_config = {"env_file": ".env", "extra": "ignore"}

    def validate_security(self):
        if self.environment == "production":
            if len(self.secret_key) < 32:
                raise RuntimeError("Production requires SECRET_KEY of at least 32 characters")
            if self.db_url.startswith("sqlite"):
                raise RuntimeError("Production requires a persistent PostgreSQL database")
            if "*" in self.cors_origins:
                raise RuntimeError("Wildcard CORS is forbidden in production")


@lru_cache
def get_settings():
    settings = Settings()
    settings.validate_security()
    if not settings.secret_key:
        # Development only; credentials/tokens are invalidated at restart.
        settings.secret_key = secrets.token_urlsafe(48)
    return settings


settings = get_settings()
