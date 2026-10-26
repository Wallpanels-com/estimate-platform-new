"""Restore a stopped-app backup into a fresh localhost QA DB and verify storage hashes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import uuid
from urllib.parse import urlsplit, urlunsplit
import psycopg2
from psycopg2 import sql
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("backup", type=Path)
args = parser.parse_args()
backup = args.backup.resolve()
manifest = json.loads((backup / "manifest.json").read_text())
for name, digest in manifest["artifacts"].items():
    path = (backup / name).resolve()
    assert path.is_relative_to(backup)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
found = {}
with tarfile.open(backup / "storage.tar.gz", "r:gz") as archive:
    for member in archive:
        if member.isfile():
            assert member.name.startswith("storage/")
            found[member.name.removeprefix("storage/")] = hashlib.sha256(archive.extractfile(member).read()).hexdigest()
assert found == manifest["storage_files"], "Storage backup is incomplete or damaged."
env = {**os.environ, **{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}}
parsed = urlsplit(env["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://"))
if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("Backup restore rehearsal is localhost-only.")
name = "wallpanels_qa_restore_" + uuid.uuid4().hex[:12]
assert re.fullmatch(r"wallpanels_qa_restore_[0-9a-f]{12}", name)
connection = psycopg2.connect(urlunsplit(parsed._replace(path="/postgres")))
connection.autocommit = True
db = None
try:
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    restore = shutil.which("pg_restore") or str(Path(env.get("LOCAL_PG_BIN", "")) / "pg_restore")
    test_env = {**env, "PGHOST": parsed.hostname, "PGPORT": str(parsed.port or 5432), "PGUSER": parsed.username or "", "PGPASSWORD": parsed.password or ""}
    subprocess.run([restore, "--exit-on-error", "--no-owner", "--no-acl", "-d", name, str(backup / "database.dump")], env=test_env, check=True)
    db = psycopg2.connect(urlunsplit(parsed._replace(path="/" + name)))
    with db.cursor() as cursor:
        cursor.execute("SELECT version_num FROM alembic_version")
        assert cursor.fetchone()[0] == "0003_uniform_users"
        counts = {}
        for table in ("users", "estimates", "estimate_images", "pricing_config", "audit_events", "document_versions"):
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
            counts[table] = cursor.fetchone()[0]
    print(json.dumps({"restored": True, "storage_hashes_verified": len(found), "tables": counts}))
finally:
    if db is not None:
        db.close()
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
    connection.close()
