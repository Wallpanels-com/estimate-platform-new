"""Railway pre-deploy: migrate the new database, then bootstrap only if empty."""
import subprocess
import sys


if __name__ == "__main__":
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    subprocess.run([sys.executable, "-m", "app.cli", "--if-empty"], check=True)
