from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    OPENAI_API_KEY: str = ""
    FRONTEND_DIST: str = ""
    STORAGE_PATH: str = "/data"
    MAX_UPLOAD_SIZE_MB: int = 20
    PRE_ESTIMATE_DESIGN: Literal["v1", "v2"] = "v2"
    ALLOWED_ORIGINS: str = "*"
    ALLOW_SELF_REGISTRATION: bool = False
    AUTO_MIGRATE: bool = False
    ENABLE_PERMANENT_DELETE: bool = False
    REQUIRE_ESTIMATE_REVISION: bool = True

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
