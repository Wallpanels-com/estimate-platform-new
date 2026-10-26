from pathlib import Path
import os, secrets, shutil, subprocess
ROOT=Path(__file__).resolve().parents[1]; os.chdir(ROOT)
python=shutil.which('python3.12')
if not python:raise SystemExit('Install Python 3.12 first; the backend pins Python 3.12-compatible dependencies.')
if not (ROOT/'.venv/bin/python').exists():subprocess.run([python,'-m','venv','.venv'],check=True)
if not (ROOT/'.env').exists():
    text=(ROOT/'.env.example').read_text().replace('change-this-local-jwt-secret',secrets.token_hex(48))
    (ROOT/'.env').write_text(text);(ROOT/'.env').chmod(0o600)
subprocess.run([str(ROOT/'.venv/bin/python'),'-m','pip','install','-r','apps/backend/requirements.txt','-c','apps/backend/constraints-local.txt'],check=True)
subprocess.run(['npm','ci','--cache','.local/npm-cache'],check=True)
print('Setup complete. Configure DATABASE_URL, start PostgreSQL, run npm run db:migrate, then npm run dev. Existing pre-Alembic databases need an approved backup and explicit --adopt-legacy first.')
