import os
from typing import Any, Dict, List
from pydantic_settings import BaseSettings
from pydantic import field_validator, AnyHttpUrl

class Settings(BaseSettings):
    PROJECT_NAME: str = "TalkFiesta Backend"
    API_V1_STR: str = "/api/v1"
    
    # Database Configuration
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "talkfiesta"
    SQLALCHEMY_DATABASE_URI: str | None = None

    @field_validator("SQLALCHEMY_DATABASE_URI", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: str | None, info) -> str:
        if isinstance(v, str) and v:
            return v
        
        data = info.data if hasattr(info, "data") else {}
        server = data.get("POSTGRES_SERVER") or os.getenv("POSTGRES_SERVER", "localhost")
        user = data.get("POSTGRES_USER") or os.getenv("POSTGRES_USER", "postgres")
        password = data.get("POSTGRES_PASSWORD") or os.getenv("POSTGRES_PASSWORD", "postgres")
        db = data.get("POSTGRES_DB") or os.getenv("POSTGRES_DB", "talkfiesta")
        
        return f"postgresql://{user}:{password}@{server}/{db}"

    # JWT & Cryptography Settings
    SECRET_KEY: str = "super-secret-key-for-development-purposes-only-please-change-in-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 1 week for easy dev testing, default is 30 mins
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Google OAuth Settings
    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None

    # Gemini API Settings
    GEMINI_API_KEY: str | None = None

    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # Deepgram API Settings
    DEEPGRAM_API_KEY: str | None = None

    # CORS Settings
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()

