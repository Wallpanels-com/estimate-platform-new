"""Explicit PostgreSQL migrations. Local by default; no production startup DDL."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def environment():
    from dotenv import dotenv_values
    return {**os.environ, **{k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adopt-legacy", action="store_true", help="Validate and stamp an existing pre-Alembic local database before upgrading.")
    parser.add_argument("--allow-remote", action="store_true", help="Only for a separately approved deployment migration.")
    args = parser.parse_args()
    env = environment()
    parsed = urlsplit(env.get("DATABASE_URL", ""))
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} and not args.allow_remote:
        raise SystemExit("Remote migrations require a separate explicit --allow-remote invocation.")
    command = [str(ROOT / ".venv/bin/python"), "-m", "alembic", "-c", "alembic.ini"]
    if args.adopt_legacy:
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise SystemExit("Legacy adoption is local-only; production adoption needs a separately reviewed runbook.")
        import psycopg2
        from sqlalchemy import inspect, create_engine
        url = env["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
        engine = create_engine(url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        if "alembic_version" in tables:
            raise SystemExit("This database already has Alembic state. Run migrate.py without --adopt-legacy.")
        required = {"users", "estimates", "estimate_zones", "line_items", "estimate_images", "voice_files", "pdf_files", "pricing_config"}
        if not required.issubset(tables):
            raise SystemExit("Legacy database is incomplete; refusing to stamp it.")
        # Validate the frozen baseline column names before recording its revision.
        import re
        sql = (ROOT / "apps/backend/alembic/baseline.sql").read_text()
        for table, body in re.findall(r"CREATE TABLE (\w+) \((.*?)\n\)", sql, re.S):
            expected = {line.strip().split()[0] for line in body.splitlines() if line.startswith("\t") and not line.lstrip().startswith(("PRIMARY", "FOREIGN", "UNIQUE", "CONSTRAINT"))}
            actual = {column["name"] for column in inspector.get_columns(table)}
            if not expected.issubset(actual):
                raise SystemExit(f"Legacy table {table} lacks columns: {sorted(expected - actual)}")
        engine.dispose()
        subprocess.run(command + ["stamp", "0001_baseline"], cwd=ROOT / "apps/backend", env=env, check=True)
    subprocess.run(command + ["upgrade", "head"], cwd=ROOT / "apps/backend", env=env, check=True)


if __name__ == "__main__":
    main()
