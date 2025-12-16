import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import List, Optional, Dict

# Find the root .env file (parent of backend folder)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

class Settings(BaseSettings):
    PROJECT_NAME: str = "Code MRI"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    TEMP_DIR: str = "temp_clones"
    GOOGLE_API_KEY: Optional[str] = None
    # Default scoring weights for the Score Agent. Values must sum to <= 1.0
    SCORE_WEIGHTS: Dict[str, float] = {
        "readability": 0.25,
        "complexity": 0.20,
        "maintainability": 0.20,
        "docs_coverage": 0.20,
        "security": 0.15,
    }

    class Config:
        env_file = str(ENV_FILE)
        env_file_encoding = 'utf-8'
        case_sensitive = True
        extra = 'ignore'  # Ignore frontend env vars like NEXT_PUBLIC_*


settings = Settings()
