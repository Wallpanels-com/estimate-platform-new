"""Backup safety: credentials stay off command lines; restores target a new DB."""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps/backend"))
os.environ.setdefault("DATABASE_URL", "postgresql://unused:unused@localhost/unused")
os.environ.setdefault("SECRET_KEY", "unit-tests-only")
from app.services import backups


class BackupSafety(unittest.TestCase):
    def test_password_is_environment_only_and_stderr_is_not_exposed(self):
        options = {"host": "localhost", "port": 5432, "dbname": "corporate", "user": "employee", "password": "sensitive-placeholder"}
        with patch.object(backups.subprocess, "run", return_value=MagicMock(returncode=0)) as run:
            backups.pg_command("pg_dump", options, "-Fc", "-f", "/tmp/unit.dump")
            args, kwargs = run.call_args
            self.assertNotIn(options["password"], str(args))
            self.assertEqual(kwargs["env"]["PGPASSWORD"], options["password"])
        with patch.object(backups.subprocess, "run", return_value=MagicMock(returncode=1, stderr=b"sensitive-placeholder")):
            with self.assertRaisesRegex(RuntimeError, "pg_dump failed") as error:
                backups.pg_command("pg_dump", options)
            self.assertNotIn(options["password"], str(error.exception))

    def test_verification_never_restores_into_working_database(self):
        options = {"host": "localhost", "port": 5432, "dbname": "corporate", "user": "employee", "password": "placeholder"}
        admin = MagicMock(); restored = MagicMock()
        restored.cursor.return_value.__enter__.return_value.fetchone.return_value = ("0003_uniform_users",)
        with patch.object(backups.psycopg2, "connect", side_effect=[admin, restored]), \
             patch.object(backups, "row_counts", return_value={"users": 7}), \
             patch.object(backups, "pg_command") as command:
            backups.verify_dump(Path("/tmp/unit.dump"), {"users": 7}, options)
            target = command.call_args.args[1]["dbname"]
            self.assertTrue(target.startswith("estimate_backup_verify_"))
            self.assertNotEqual(target, options["dbname"])
            self.assertNotIn("--clean", command.call_args.args)
            restored.close.assert_called_once()
