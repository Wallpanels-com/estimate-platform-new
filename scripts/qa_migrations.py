"""Exercise all migrations in a newly created, isolated localhost QA database."""
import os
from pathlib import Path
import re
import subprocess
import uuid
from urllib.parse import urlsplit, urlunsplit
import psycopg2
from psycopg2 import sql
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
env = {**os.environ, **{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}}
url = env["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
parsed = urlsplit(url)
if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
    raise SystemExit("Only a localhost QA database is permitted.")
name = "wallpanels_qa_migrations_" + uuid.uuid4().hex[:12]
assert re.fullmatch(r"wallpanels_qa_migrations_[0-9a-f]{12}", name)
admin_url = urlunsplit(parsed._replace(path="/postgres"))
test_url = urlunsplit(parsed._replace(path="/" + name))
connection = psycopg2.connect(admin_url)
connection.autocommit = True
db = None
try:
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    test_env = {**env, "DATABASE_URL": test_url}
    command = [str(ROOT / ".venv/bin/python"), "-m", "alembic", "upgrade", "head"]
    subprocess.run(command, env=test_env, cwd=ROOT / "apps/backend", check=True)
    subprocess.run(command, env=test_env, cwd=ROOT / "apps/backend", check=True)
    with psycopg2.connect(test_url) as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT version_num FROM alembic_version")
            assert cursor.fetchone()[0] == "0003_uniform_users"
            cursor.execute("SELECT COUNT(*) FROM estimates")
            assert cursor.fetchone()[0] == 0
            cursor.execute("SELECT COUNT(*) FROM users")
            assert cursor.fetchone()[0] == 0
            ident = str(uuid.uuid4())
            cursor.execute("INSERT INTO audit_events(id,actor_name,entity,entity_id,action,changes) VALUES (%s,'QA','QA','QA','create','{}')", (ident,))
        db.commit()
        try:
            with db.cursor() as cursor:
                cursor.execute("DELETE FROM audit_events WHERE id = %s", (ident,))
            raise AssertionError("Audit rows must be immutable")
        except psycopg2.Error:
            db.rollback()
    print("Fresh database migrations, repeat upgrade, empty initial data and immutable audit trigger verified.")
finally:
    if db is not None:
        db.close()
    # Exact ephemeral database created by this invocation; no existing DB is targeted.
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
    connection.close()
