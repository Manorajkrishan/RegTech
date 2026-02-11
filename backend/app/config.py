from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "ESG RegTech Platform"
    debug: bool = True
    db_url: str = "sqlite+aiosqlite:///./esg_platform.db"
    upload_dir: Path = Path("uploads")
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    emission_factors_path: Path = Path("data/emission_factors.json")

    class Config:
        env_file = ".env"


settings = Settings()
