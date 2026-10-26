"""Explicit first-employee bootstrap for an approved, migrated empty deployment."""
import asyncio
import os
from sqlalchemy import select, func, text
from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.auth import UserCreate
from app.services import audit


async def main():
    data = UserCreate(email=os.environ.get("BOOTSTRAP_EMAIL", ""), name=os.environ.get("BOOTSTRAP_NAME", ""), password=os.environ.get("BOOTSTRAP_PASSWORD", ""))
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(18724301)"))
        if (await db.execute(select(func.count()).select_from(User))).scalar():
            raise SystemExit("Users already exist. First-user bootstrap refused; use Team accounts.")
        db.info["actor"] = {"id": None, "name": "First employee bootstrap"}
        db.add(User(email=str(data.email).lower(), name=data.name, role="user", password_hash=get_password_hash(data.password)))
        await db.commit()
    await engine.dispose()
    print("First User account created. Remove the temporary BOOTSTRAP_* variables.")


if __name__ == "__main__":
    asyncio.run(main())
