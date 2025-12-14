import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List, Optional

# Find the root .env file (parent of backend folder)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str = "Code MRI"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    TEMP_DIR: str = "temp_clones"
    GOOGLE_API_KEY: Optional[str] = None

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = 'ignore'  # Ignore frontend env vars like NEXT_PUBLIC_*


settings = Settings()
