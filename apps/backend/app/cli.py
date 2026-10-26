"""Explicit first-employee bootstrap for an approved, migrated empty deployment."""
import asyncio
import os
import argparse
import re
from sqlalchemy import select, func, text
from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User
from app.schemas.auth import UserCreate
from app.services import audit


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--if-empty", action="store_true")
    args = parser.parse_args()
    async with AsyncSessionLocal() as db:
        await db.execute(text("SELECT pg_advisory_xact_lock(18724301)"))
        if (await db.execute(select(func.count()).select_from(User))).scalar():
            if args.if_empty:
                print("Employee accounts already initialized; bootstrap skipped.")
                await engine.dispose()
                return
            raise SystemExit("Users already exist. First-user bootstrap refused; use Team accounts.")
        password_hash = os.environ.get("BOOTSTRAP_PASSWORD_HASH", "")
        if password_hash and not re.fullmatch(r"\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}", password_hash):
            raise SystemExit("Invalid bootstrap password hash.")
        data = UserCreate(email=os.environ.get("BOOTSTRAP_EMAIL", ""), name=os.environ.get("BOOTSTRAP_NAME", ""), password="Hash-bootstrap-placeholder" if password_hash else os.environ.get("BOOTSTRAP_PASSWORD", ""))
        db.info["actor"] = {"id": None, "name": "First employee bootstrap"}
        db.add(User(email=str(data.email).lower(), name=data.name, role="user", password_hash=password_hash or get_password_hash(data.password)))
        await db.commit()
    await engine.dispose()
    print("First User account created. Remove the temporary BOOTSTRAP_* variables.")


if __name__ == "__main__":
    asyncio.run(main())
