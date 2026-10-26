#!/usr/bin/env python3
"""Fail when the source tree is unsafe or incomplete for a future Git commit."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "package.json",
    "package-lock.json",
    ".env.example",
    "Dockerfile",
    "railway.toml",
    "apps/frontend/src/main.tsx",
    "apps/backend/app/main.py",
    "apps/backend/app/services/rule_engine.py",
    "apps/backend/app/services/pricebook_service.py",
    "apps/backend/app/services/pre_estimate_service.py",
    "apps/backend/app/services/final_estimate_service.py",
    "apps/backend/app/services/passport_service.py",
    "apps/backend/app/templates/project_passport_template.xlsx",
    "apps/backend/assets/proposals/final-shared-title.png",
    "apps/backend/assets/proposals/company-slides.pdf",
)
FORBIDDEN_PARTS = {
    ".env",
    ".local",
    ".venv",
    "node_modules",
    "__pycache__",
    "dist",
    "output",
    "outputs",
}
FORBIDDEN_SUFFIXES = {".pyc", ".log", ".dump", ".backup", ".sqlite", ".db"}


def source_files() -> list[Path]:
    if (ROOT / ".git").is_dir():
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        return [ROOT / value.decode() for value in result.stdout.split(b"\0") if value]
    ignored = {".git", ".local", ".venv", "node_modules", "dist", "output", "outputs"}
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in ignored for part in path.relative_to(ROOT).parts)
    ]


def main() -> None:
    errors: list[str] = []
    for name in REQUIRED:
        if not (ROOT / name).is_file():
            errors.append(f"missing required file: {name}")

    files = source_files()
    for path in files:
        relative = path.relative_to(ROOT)
        if any(part in FORBIDDEN_PARTS for part in relative.parts):
            errors.append(f"generated/private path is not ignored: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            errors.append(f"generated/private file is not ignored: {relative}")
        if path.stat().st_size >= 95 * 1024 * 1024:
            errors.append(f"file is too large for normal GitHub storage: {relative}")

    manifest_path = ROOT / "apps/backend/assets/proposals/company-slides.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        corporate = ROOT / "apps/backend/assets/proposals/company-slides.pdf"
        if corporate.is_file():
            digest = hashlib.sha256(corporate.read_bytes()).hexdigest()
            expected = manifest.get("sha256")
            if expected and digest != expected:
                errors.append("corporate PDF hash does not match its manifest")
            if manifest.get("pages") != 13:
                errors.append("corporate PDF manifest must require exactly 13 pages")

    text_suffixes = {".py", ".js", ".mjs", ".ts", ".tsx", ".json", ".md", ".toml", ".yml", ".yaml"}
    forbidden_text = (
        "Local-" + "WallPanels-2026!",
        "/Users/" + "user/Desktop/",
    )
    for path in files:
        if path.suffix.lower() not in text_suffixes:
            continue
        text = path.read_text(errors="ignore")
        for value in forbidden_text:
            if value in text:
                errors.append(f"machine-specific or credential value in {path.relative_to(ROOT)}")

    if errors:
        raise SystemExit("Repository verification failed:\n- " + "\n- ".join(sorted(set(errors))))
    print(f"Repository verification passed: {len(files)} source files checked.")


if __name__ == "__main__":
    main()
