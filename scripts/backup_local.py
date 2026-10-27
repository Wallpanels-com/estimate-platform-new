"""Back up localhost data and retained files; generated PDFs are excluded."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tarfile
from urllib.parse import urlsplit, unquote
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
env = {**os.environ, **{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}}
parsed = urlsplit(env.get("DATABASE_URL", ""))
if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("Backups from this helper are restricted to localhost.")
with socket.socket() as listener:
    if listener.connect_ex(("127.0.0.1", int(env.get("BACKEND_PORT", "8010")))) == 0:
        raise SystemExit("Stop the local application before a matched DB/storage backup: npm run stop")
storage = Path(env.get("STORAGE_PATH", str(ROOT / ".local/storage")))
if not storage.is_absolute():
    storage = (ROOT / "apps/backend" / storage).resolve()
if not storage.is_dir():
    raise SystemExit("Configured storage directory does not exist.")
target = ROOT / ".local/backups" / ("corporate-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
target.mkdir(parents=True, mode=0o700)
pg_env = {**env, "PGHOST": parsed.hostname, "PGPORT": str(parsed.port or 5432),
          "PGDATABASE": unquote(parsed.path.lstrip("/")), "PGUSER": unquote(parsed.username or "")}
if parsed.password:
    pg_env["PGPASSWORD"] = unquote(parsed.password)
binary = shutil.which("pg_dump") or str(Path(env.get("LOCAL_PG_BIN", "")) / "pg_dump")
subprocess.run([binary, "-Fc", "--no-owner", "--no-acl", "--file", str(target / "database.dump")], env=pg_env, check=True)
with tarfile.open(target / "storage.tar.gz", "w:gz") as archive:
    archive.add(storage, arcname="storage", filter=lambda member: None if Path(member.name).suffix.lower() == '.pdf' or member.name.startswith('storage/pdfs') else member)
manifest = {"commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
            "storage_files": {}, "artifacts": {}, "pdf_presentations_excluded": True}
for path in storage.rglob("*"):
    if path.is_file() and path.suffix.lower() != '.pdf' and path.relative_to(storage).parts[0] != 'pdfs':
        manifest["storage_files"][str(path.relative_to(storage))] = hashlib.sha256(path.read_bytes()).hexdigest()
for path in target.iterdir():
    if path.is_file():
        path.chmod(0o600)
        manifest["artifacts"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
(target / "manifest.json").write_text(json.dumps(manifest, indent=2))
(target / "manifest.json").chmod(0o600)
print("Matched database/storage backup saved to", target.relative_to(ROOT))
