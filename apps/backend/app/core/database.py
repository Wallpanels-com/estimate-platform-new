from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
from fastapi import Request

# Convert postgres:// to postgresql+asyncpg://
db_url = settings.DATABASE_URL.replace("postgres://", "postgresql+asyncpg://").replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db(request: Request):
    async with AsyncSessionLocal() as session:
        request.state.estimate_session = session
        session.info["expected_revision"] = request.headers.get("If-Match")
        session.info["write_request"] = request.method not in {"GET", "HEAD", "OPTIONS"}
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
