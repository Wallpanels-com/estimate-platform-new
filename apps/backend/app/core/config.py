from pydantic import field_validator, Field
from pydantic_settings import BaseSettings
from typing import Literal
from uuid import UUID


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = Field(default="", repr=False)
    MANUAL_IMPORT_GROQ_API_KEY: str = Field(default="", repr=False)
    MANUAL_IMPORT_AI_MODEL: str = "openai/gpt-oss-120b"
    HR_AI_MODEL: str = "openai/gpt-oss-120b"
    FRONTEND_DIST: str = ""
    AGENTATION_USER_ID: UUID | None = None
    ACCESS_MANAGER_USER_ID: UUID | None = None
    STORAGE_PATH: str = "/data"
    MAX_UPLOAD_SIZE_MB: int = 20
    PDF_PHOTO_OPTIMIZATION_ENABLED: bool = True
    PRE_ESTIMATE_DESIGN: Literal["v1", "v2"] = "v2"
    ALLOWED_ORIGINS: str = "*"
    ALLOW_SELF_REGISTRATION: bool = False
    PORTAL_AUTH_ENABLED: bool = False
    PORTAL_EMBED_ENABLED: bool = False
    PORTAL_BASE_URL: str = "https://edu.wallpanels.com"
    PORTAL_BRIDGE_SECRET: str = Field(default="", repr=False)
    AUTO_MIGRATE: bool = False
    ENABLE_PERMANENT_DELETE: bool = False
    REQUIRE_ESTIMATE_REVISION: bool = True
    BACKUP_ENABLED: bool = False
    BACKUP_ENDPOINT: str = ""
    BACKUP_BUCKET: str = ""
    BACKUP_REGION: str = "auto"
    BACKUP_ACCESS_KEY_ID: str = ""
    BACKUP_SECRET_ACCESS_KEY: str = ""
    BACKUP_ADDRESSING_STYLE: str = "path"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def use_async_postgres_driver(cls, value: str) -> str:
        """Accept standard provider URLs while keeping SQLAlchemy async."""
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        return value

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
