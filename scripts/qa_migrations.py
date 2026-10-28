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
from alembic.script import ScriptDirectory

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
            assert cursor.fetchone()[0] == ScriptDirectory(str(ROOT / "apps/backend/alembic")).get_current_head()
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
    subprocess.run(command[:-2] + ["downgrade", "0003_uniform_users"], env=test_env, cwd=ROOT / "apps/backend", check=True)
    employee, pre, final, history_id = [str(uuid.uuid4()) for _ in range(4)]
    with db.cursor() as cursor:
        cursor.execute("INSERT INTO users(id,email,name,role,password_hash,onboarding_completed) VALUES (%s,'fixture.employee','Example Employee','user','not-a-real-account',true)", (employee,))
        cursor.execute("INSERT INTO audit_events(id,actor_name,entity,entity_id,action,changes) VALUES (%s,'Fixture','users',%s,'update',%s)",
                       (history_id,employee,'{"name":{"before":"Old employee label","after":"Example Employee"}}'))
        for ident,kind,source,total in [(pre,'pre',None,50),(final,'final',pre,75)]:
            cursor.execute("INSERT INTO estimates(id,user_id,type,source_estimate_id,title,prepared_by,created_by_name,updated_by_name,subtotal,final_total,updated_at,status,manual_override) VALUES (%s,%s,%s,%s,'Preserved title','Old employee label','Old employee label','Old employee label',%s,%s,'2026-01-01T00:00:00Z','draft',false)", (ident,employee,kind,source,total,total))
    db.commit()
    subprocess.run(command, env=test_env, cwd=ROOT / "apps/backend", check=True)
    with db.cursor() as cursor:
        cursor.execute("SELECT type,prepared_by,created_by_name,updated_by_name,subtotal,final_total,updated_at,title FROM estimates ORDER BY type")
        for kind,prepared,creator,editor,subtotal,total,updated,title in cursor.fetchall():
            assert prepared == creator == editor == 'Example Employee'
            assert subtotal == total == (75 if kind=='final' else 50)
            assert updated.year==2026 and updated.month==1 and updated.day==1 and title=='Preserved title'
        cursor.execute("SELECT changes FROM audit_events WHERE id=%s",(history_id,))
        assert cursor.fetchone()[0]['name']['before']=='Old employee label'
        cursor.execute("SELECT count(*) FROM audit_events WHERE action='author_names_updated'")
        assert cursor.fetchone()[0]==2
    db.commit()
    subprocess.run(command, env=test_env, cwd=ROOT / "apps/backend", check=True)
    print("Fresh/repeat migrations, immutable history, and populated Pre/Final author correction with unchanged prices/dates verified.")
finally:
    if db is not None:
        db.close()
    # Exact ephemeral database created by this invocation; no existing DB is targeted.
    with connection.cursor() as cursor:
        cursor.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(name)))
    connection.close()
