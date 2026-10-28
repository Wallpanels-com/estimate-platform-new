"""Repeatable PostgreSQL measurements in a disposable LOCAL schema, never production."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import statistics
import sys
import time
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))
from dotenv import load_dotenv
load_dotenv(ROOT / '.env')
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.database import Base
import app.models
from app.models.estimate import Estimate
from app.models.user import User
from app.api.v1.estimates import list_estimates, list_trash

async def main(label):
    url = os.environ['DATABASE_URL']
    if urlsplit(url.replace('postgresql+asyncpg:', 'postgresql:')).hostname not in ('localhost', '127.0.0.1', '::1'):
        raise SystemExit('Only loopback PostgreSQL is allowed.')
    url = url.replace('postgres://', 'postgresql+asyncpg://').replace('postgresql://', 'postgresql+asyncpg://')
    schema = 'audit_' + uuid.uuid4().hex
    admin = create_async_engine(url)
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={'server_settings': {'search_path': schema}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    queries = []
    event.listen(engine.sync_engine, 'before_cursor_execute', lambda c, cu, stmt, params, ctx, many: queries.append(stmt))
    report = {'label': label, 'environment': 'isolated loopback PostgreSQL schema', 'samples': []}
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessions() as db:
            user = User(email='audit.local', name='Local audit', password_hash='not-a-login', role='user')
            db.add(user)
            await db.flush()
            for i in range(100):
                root = Estimate(user_id=user.id, type='pre', title=f'Audit {i}', branch_state={'active_mode': 'final'}, subtotal=100, final_total=100)
                db.add(root)
                await db.flush()
                db.add(Estimate(user_id=user.id, source_estimate_id=root.id, type='final', title=f'Audit {i}', subtotal=100, final_total=100))
            await db.commit()
        for operation in (list_estimates, list_trash):
            durations, counts = [], []
            for _ in range(5):
                async with sessions() as db:
                    queries.clear()
                    start = time.perf_counter()
                    rows = await operation(db=db, current_user=user)
                    durations.append((time.perf_counter() - start) * 1000)
                    counts.append(len(queries))
                if operation is list_estimates:
                    assert len(rows) == 100 and all(row.type == 'final' for row in rows)
            report['samples'].append({'operation': operation.__name__, 'projects': len(rows), 'sql_queries': counts, 'median_ms': round(statistics.median(durations), 2), 'runs_ms': [round(x, 2) for x in durations]})
        output = ROOT / '.local/audit' / f'performance-{label}.json'
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', choices=['before', 'after'], required=True)
    asyncio.run(main(parser.parse_args().label))
