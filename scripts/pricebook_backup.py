"""Local-only Price Book backup and explicit rollback. Never connects remotely."""
from pathlib import Path
from urllib.parse import urlsplit, unquote
import argparse, asyncio, datetime, hashlib, importlib.util, json, os, shutil, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('local_dev', ROOT/'scripts/dev.py')
dev = importlib.util.module_from_spec(spec); spec.loader.exec_module(dev)
env = dev.environment()
parsed = urlsplit(env['DATABASE_URL'])
if parsed.hostname not in ('127.0.0.1', 'localhost', '::1'):
    raise SystemExit('This tool only supports the local database.')

async def pricing_rows(restore=None):
    sys.path.insert(0, str(ROOT/'apps/backend'))
    os.environ.update(env)
    from app.core.database import AsyncSessionLocal, engine
    from app.models.estimate import PricingConfig
    from sqlalchemy import select, delete
    async with AsyncSessionLocal() as db:
        if restore is None:
            rows=(await db.execute(select(PricingConfig))).scalars().all()
            result=[{'id':str(r.id),'config':r.config,'updated_by_name':r.updated_by_name,'updated_at':r.updated_at.isoformat()} for r in rows]
        else:
            import uuid
            await db.execute(delete(PricingConfig))
            for row in restore:
                db.add(PricingConfig(id=uuid.UUID(row['id']),config=row['config'],updated_by_name=row['updated_by_name'],updated_at=datetime.datetime.fromisoformat(row['updated_at'])))
            await db.commit(); result=None
    await engine.dispose()
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restore-pricing',type=Path)
    parser.add_argument('--restore-source',type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if args.restore_pricing:
        records=json.loads((args.restore_pricing/'pricing-rows.json').read_text())
        if not args.apply:
            print(f'Dry run: restore {len(records)} pricing_config rows only; estimates and files are retained. Add --apply to execute.');return
        asyncio.run(pricing_rows(records));print('Local Price Book data restored.');return
    if args.restore_source:
        backup=args.restore_source.resolve()
        changes=json.loads((backup/'change-files.json').read_text())
        if not args.apply:
            print(f'Dry run: restore {len(changes["changed"])} files and remove {len(changes["added"])} feature files. Add --apply to execute.');return
        for name in changes['changed']:
            dest=(ROOT/name).resolve(); assert dest.is_relative_to(ROOT)
            shutil.copy2(backup/'source'/name,dest)
        for name in changes['added']:
            dest=(ROOT/name).resolve(); assert dest.is_relative_to(ROOT)
            dest.unlink(missing_ok=True)
        print('Local feature source restored. Run npm run build and restart the local app.');return
    backup=ROOT/'.local/backups'/('pricebook-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S'))
    backup.mkdir(parents=True)
    files=[]
    for folder in ['apps/frontend/src','apps/backend/app','tests','docs']:
        files += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [ROOT/'package.json']
    manifest={}
    for source in files:
        name=str(source.relative_to(ROOT));dest=backup/'source'/name
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        manifest[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    (backup/'source-sha256.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (backup/'pricing-rows.json').write_text(json.dumps(asyncio.run(pricing_rows()),indent=2,default=str)+'\n')
    pg_bin=Path(env.get('LOCAL_PG_BIN','/opt/homebrew/opt/postgresql@16/bin'))
    binary=shutil.which('pg_dump') or str(pg_bin/'pg_dump')
    pg_env={**env,'PGHOST':parsed.hostname,'PGPORT':str(parsed.port or 5432),'PGDATABASE':unquote(parsed.path.lstrip('/')),'PGUSER':unquote(parsed.username or os.environ.get('USER',''))}
    if parsed.password:pg_env['PGPASSWORD']=unquote(parsed.password)
    subprocess.run([binary,'-Fc','--file',str(backup/'database.dump')],env=pg_env,check=True)
    print('Backup complete:',backup.relative_to(ROOT))
    print('Includes source hashes, original Price Book rows and a full local PostgreSQL dump.')

if __name__=='__main__':main()
