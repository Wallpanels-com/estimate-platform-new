"""One-time LOCAL-only logical DB copy. Does not alter source database or files."""
from pathlib import Path
from urllib.parse import urlsplit,unquote
import argparse,os,subprocess
from dotenv import dotenv_values
import psycopg2
from psycopg2 import sql

p=argparse.ArgumentParser();p.add_argument('--source-env',required=True);p.add_argument('--source-storage',required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1];target=dotenv_values(root/'.env');source=dotenv_values(args.source_env)
src=urlsplit(source['DATABASE_URL']);dst=urlsplit(target['DATABASE_URL'])
assert src.hostname in ('localhost','127.0.0.1') and dst.hostname in ('localhost','127.0.0.1'), 'Only loopback databases may be copied.'
assert src.path!=dst.path,'Source and target database must differ.'
def connect(url,database):return psycopg2.connect(host=url.hostname,port=url.port,user=unquote(url.username),password=unquote(url.password),dbname=database)
name=dst.path.lstrip('/')
with connect(dst,'postgres') as conn:
    with conn.cursor() as cur:cur.execute('SELECT 1 FROM pg_database WHERE datname=%s',(name,));exists=cur.fetchone()
if exists:raise SystemExit('Target already exists. Import not repeated; no data changed.')
conn=connect(dst,'postgres');conn.autocommit=True
with conn.cursor() as cur:cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
conn.close()
pg=Path(target['LOCAL_PG_BIN']);env=dict(os.environ,PGHOST=src.hostname,PGPORT=str(src.port),PGUSER=unquote(src.username),PGPASSWORD=unquote(src.password))
backup=root/'.local/legacy-backup.dump'
with backup.open('wb') as f:subprocess.run([str(pg/'pg_dump'),'-Fc','--no-owner','--no-acl',src.path.lstrip('/')],env=env,stdout=f,check=True)
env.update(PGHOST=dst.hostname,PGPORT=str(dst.port),PGUSER=unquote(dst.username),PGPASSWORD=unquote(dst.password))
subprocess.run([str(pg/'pg_restore'),'--no-owner','--no-acl','-d',name,str(backup)],env=env,check=True)
with connect(dst,name) as conn:
    with conn.cursor() as cur:
        for table in ('estimate_images','voice_files','pdf_files'):
            cur.execute(sql.SQL('UPDATE {} SET file_path=replace(file_path,%s,%s) WHERE file_path LIKE %s').format(sql.Identifier(table)),(str(Path(args.source_storage).resolve()),target['STORAGE_PATH'],str(Path(args.source_storage).resolve())+'/%'))
print('Local database copied; stored paths now point to the new local storage. Source retained.')
