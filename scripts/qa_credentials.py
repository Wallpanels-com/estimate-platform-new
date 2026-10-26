"""Credentials for explicit localhost QA scripts, supplied outside source control."""

import os
import json
import secrets
from pathlib import Path

from dotenv import dotenv_values


def qa_credentials(create_disposable: bool = False) -> tuple[str, str]:
    root = Path(__file__).resolve().parents[1]
    local = dotenv_values(root / ".env")
    email = (
        os.environ.get("LOCAL_QA_EMAIL") or local.get("LOCAL_QA_EMAIL") or ""
    ).strip()
    password = (
        os.environ.get("LOCAL_QA_PASSWORD")
        or local.get("LOCAL_QA_PASSWORD")
        or ""
    )
    if email and password:
        return email, password
    credential_file = root / ".local/qa-credentials.json"
    if credential_file.is_file():
        saved = json.loads(credential_file.read_text())
        if not saved["email"].endswith(".invalid"):
            return saved["email"], saved["password"]
    if create_disposable:
        credential_file.parent.mkdir(parents=True, exist_ok=True)
        saved = {
            "email": f"qa-local-{secrets.token_hex(6)}@example.com",
            "password": secrets.token_urlsafe(32),
        }
        credential_file.write_text(json.dumps(saved))
        credential_file.chmod(0o600)
        return saved["email"], saved["password"]
    raise SystemExit(
        "Set LOCAL_QA_EMAIL and LOCAL_QA_PASSWORD in the ignored .env or shell "
        "before running this localhost QA script."
    )
