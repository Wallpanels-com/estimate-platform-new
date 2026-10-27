"""Off-volume PostgreSQL + immutable file backups to a private Railway Bucket.

No restore into the live database is exposed. Verification creates a uniquely
named, empty database, restores there, compares all row counts, then drops ONLY
that verification database. Customer databases are never overwritten.
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
from urllib.parse import urlsplit, unquote
import uuid

import psycopg2
from psycopg2 import sql
from app.core.config import settings

log = logging.getLogger(__name__)
LOCK = 18724319
PREFIX = "wallpanels-backups/"


def connection_options():
    parsed = urlsplit(settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
    return dict(host=parsed.hostname, port=parsed.port or 5432,
                dbname=unquote(parsed.path.lstrip("/")), user=unquote(parsed.username or ""),
                password=unquote(parsed.password or ""))


def pg_command(command, options, *arguments):
    env = {**os.environ, "PGHOST": options["host"], "PGPORT": str(options["port"]),
           "PGDATABASE": options["dbname"], "PGUSER": options["user"], "PGPASSWORD": options["password"]}
    result = subprocess.run([command, *arguments], env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, timeout=300)
    if result.returncode:
        # Do not log connection strings or database contents from tool stderr.
        raise RuntimeError(f"{command} failed; backup was not accepted.")


def client():
    import boto3
    from botocore.config import Config
    if not settings.BACKUP_ENABLED or not all((settings.BACKUP_ENDPOINT, settings.BACKUP_BUCKET,
                                               settings.BACKUP_ACCESS_KEY_ID, settings.BACKUP_SECRET_ACCESS_KEY)):
        raise RuntimeError("Private backup storage is not configured.")
    return boto3.client("s3", endpoint_url=settings.BACKUP_ENDPOINT,
        region_name=settings.BACKUP_REGION, aws_access_key_id=settings.BACKUP_ACCESS_KEY_ID,
        aws_secret_access_key=settings.BACKUP_SECRET_ACCESS_KEY,
        config=Config(s3={"addressing_style": settings.BACKUP_ADDRESSING_STYLE},
                      connect_timeout=15, read_timeout=120, retries={"max_attempts": 3}))


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def row_counts(cursor):
    cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
    names = [row[0] for row in cursor.fetchall()]
    result = {}
    for name in names:
        cursor.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(name)))
        result[name] = cursor.fetchone()[0]
    return result


def verify_dump(dump, expected, options):
    ident = "estimate_backup_verify_" + uuid.uuid4().hex
    created = False
    admin = psycopg2.connect(**options); admin.autocommit = True
    try:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(ident)))
            created = True
        restored = {**options, "dbname": ident}
        pg_command("pg_restore", restored, "--exit-on-error", "--no-owner", "--no-acl", "-d", ident, str(dump))
        from contextlib import closing
        with closing(psycopg2.connect(**restored)) as connection:
            with connection.cursor() as cursor:
                if row_counts(cursor) != expected:
                    raise RuntimeError("Restored row counts do not match the backup snapshot.")
                cursor.execute("SELECT version_num FROM alembic_version")
                if cursor.fetchone()[0] != "0003_uniform_users":
                    raise RuntimeError("Restored schema version does not match.")
    finally:
        if created:
            # The identifier comes ONLY from the UUID generated above, never input.
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(ident)))
        admin.close()


def status_path():
    target = Path(settings.STORAGE_PATH) / "operations" / "backups.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def status():
    try:
        return json.loads(status_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"enabled": settings.BACKUP_ENABLED, "backups": []}


def save_status(value):
    path = status_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.chmod(0o600)
    temporary.replace(path)


def create_backup(verify=False):
    storage = Path(settings.STORAGE_PATH).resolve()
    options = connection_options()
    # Session lock serializes manual and daily backups across processes.
    connection = psycopg2.connect(**options); connection.autocommit = True
    phase = "configuration"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (LOCK,))
            if not cursor.fetchone()[0]:
                raise RuntimeError("A backup is already running. Try again later.")
        s3 = client()
        with tempfile.TemporaryDirectory(prefix="wallpanels-backup-") as directory:
            phase = "database snapshot"
            work = Path(directory); dump = work / "database.dump"
            connection.autocommit = False
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                cursor.execute("SELECT pg_export_snapshot()")
                snapshot = cursor.fetchone()[0]
                counts = row_counts(cursor)
                references = set()
                for table in ("estimate_images", "voice_files", "pdf_files", "document_versions"):
                    cursor.execute(sql.SQL("SELECT file_path FROM {} WHERE file_path IS NOT NULL").format(sql.Identifier(table)))
                    references.update(row[0] for row in cursor.fetchall())
                pg_command("pg_dump", options, "-Fc", "--no-owner", "--no-acl", "--snapshot=" + snapshot, "-f", str(dump))
            connection.rollback()
            paths = {"database.dump": dump}
            phase = "file snapshot"
            for name in sorted(references):
                path = Path(name).resolve()
                if not path.is_relative_to(storage) or not path.is_file():
                    raise RuntimeError("A saved document or uploaded file is missing. Backup was not accepted.")
                paths["storage/" + str(path.relative_to(storage))] = path
            # Include the exact templates and corporate PDF used by this release.
            backend = Path(__file__).resolve().parents[2]
            for folder in (backend / "assets", backend / "app/templates"):
                for path in folder.rglob("*"):
                    if path.is_file():
                        paths["release/" + str(path.relative_to(backend))] = path
            manifest = {"created_at": datetime.now(timezone.utc).isoformat(), "tables": counts,
                        "commit": os.environ.get("RAILWAY_GIT_COMMIT_SHA", "local"), "files": {}}
            archive = work / "backup.tar.gz"
            with tarfile.open(archive, "w:gz") as output:
                for name, path in paths.items():
                    before = path.stat()
                    digest = checksum(path)
                    output.add(path, arcname=name, recursive=False)
                    after = path.stat()
                    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                        raise RuntimeError("A file changed during backup. Retry after the export completes.")
                    manifest["files"][name] = digest
                data = json.dumps(manifest, indent=2).encode()
                import io
                info = tarfile.TarInfo("manifest.json"); info.size = len(data)
                output.addfile(info, io.BytesIO(data))
            pg_command("pg_restore", options, "--list", str(dump))
            if verify:
                phase = "isolated restore test"
                verify_dump(dump, counts, options)
            ident = uuid.uuid4().hex
            key = PREFIX + datetime.now(timezone.utc).strftime("%Y/%m/%d/") + ident + ".tar.gz"
            digest = checksum(archive)
            phase = "private bucket upload"
            with archive.open("rb") as stream:
                s3.put_object(Bucket=settings.BACKUP_BUCKET, Key=key, Body=stream,
                              Metadata={"sha256": digest, "backup-id": ident})
            remote = s3.head_object(Bucket=settings.BACKUP_BUCKET, Key=key)
            if remote["ContentLength"] != archive.stat().st_size or remote["Metadata"].get("sha256") != digest:
                raise RuntimeError("Remote backup verification failed.")
            # Read the stored archive back before declaring success.
            restored_archive = work / "remote.tar.gz"
            phase = "download verification"
            s3.download_file(settings.BACKUP_BUCKET, key, str(restored_archive))
            if checksum(restored_archive) != digest:
                raise RuntimeError("Downloaded backup checksum does not match.")
            with tarfile.open(restored_archive) as stored:
                for name, expected in manifest["files"].items():
                    if hashlib.sha256(stored.extractfile(name).read()).hexdigest() != expected:
                        raise RuntimeError("Stored backup contains a damaged file.")
            row = {"id": ident, "key": key, "created_at": manifest["created_at"], "sha256": digest,
                   "bytes": archive.stat().st_size, "files": len(paths), "tables": counts,
                   "restore_tested": verify, "download_verified": True}
            previous = status()
            save_status({"enabled": True, "last_success_at": row["created_at"], "last_error": None,
                         "backups": [row, *previous.get("backups", [])][:100]})
            log.info("Private backup completed: %s; %s files; restore tested=%s", ident, len(paths), verify)
            return row
    except Exception as error:
        log.error("Private backup failed during %s (%s)", phase, type(error).__name__)
        raise
    finally:
        connection.close()


async def daily_backups():
    await asyncio.sleep(10)
    while True:
        try:
            previous = status()
            last = previous.get("last_success_at")
            due = not last or (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() >= 86400
            if due:
                await asyncio.to_thread(create_backup)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            log.error("Private daily backup failed: %s", type(error).__name__)
            previous = status(); previous["last_error"] = "Backup failed; inspect the backup service configuration and storage."
            save_status(previous)
        await asyncio.sleep(3600)
