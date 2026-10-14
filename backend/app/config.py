from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "RegTech Prototype"
    debug: bool = False
    db_url: str = "sqlite+aiosqlite:///./esg_platform.db"
    upload_dir: Path = Path("uploads")
    max_upload_size: int = 10 * 1024 * 1024
    allowed_origins: list[str] = ["http://localhost:3000"]

settings = Settings()
