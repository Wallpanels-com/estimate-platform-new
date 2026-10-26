"""Create the three requested local employee accounts; never reset existing accounts."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlsplit
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
env = dotenv_values(ROOT / ".env")
os.environ.update({k: v for k, v in env.items() if v is not None})
if urlsplit(os.environ.get("DATABASE_URL", "")).hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("This bootstrap tool only supports the local database.")
sys.path.insert(0, str(ROOT / "apps/backend"))
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine
from app.core.security import get_password_hash
from app.models.user import User
from app.services import audit


async def main():
    credentials = []
    async with AsyncSessionLocal() as db:
        db.info["actor"] = {"id": None, "name": "Local employee bootstrap"}
        for email, name in [("owner@wallpanels.com", "Owner"), ("katya@wallpanels.com", "Katya"), ("igor@wallpanels.com", "Igor")]:
            existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if existing:
                print(f"Preserved existing account: {email}")
                continue
            password = secrets.token_urlsafe(18)
            db.add(User(email=email, name=name, role="user", is_active=True, password_hash=get_password_hash(password)))
            credentials.append({"email": email, "name": name, "password": password})
        await db.commit()
    if credentials:
        target = ROOT / ".local/employee-access.json"
        if target.exists():
            raise SystemExit("Credential output already exists; new credentials were not overwritten. Use admin password reset if needed.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(credentials, indent=2))
        target.chmod(0o600)
        print("Local account credentials saved privately to .local/employee-access.json (ignored by Git).")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
