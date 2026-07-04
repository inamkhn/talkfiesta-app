import os
from typing import Any, Dict
from pydantic_settings import BaseSettings
from pydantic import field_validator

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
        
        # Extract from info.data (Pydantic v2 behavior)
        # Fall back to using default environment variables if values are missing
        data = info.data if hasattr(info, "data") else {}
        server = data.get("POSTGRES_SERVER") or os.getenv("POSTGRES_SERVER", "localhost")
        user = data.get("POSTGRES_USER") or os.getenv("POSTGRES_USER", "postgres")
        password = data.get("POSTGRES_PASSWORD") or os.getenv("POSTGRES_PASSWORD", "postgres")
        db = data.get("POSTGRES_DB") or os.getenv("POSTGRES_DB", "talkfiesta")
        
        return f"postgresql://{user}:{password}@{server}/{db}"

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
