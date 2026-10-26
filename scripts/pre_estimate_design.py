#!/usr/bin/env python3
"""Change only the local PDF design flag; never access the database."""

from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]
if len(sys.argv) != 2 or sys.argv[1] not in ("v1", "v2"):
    raise SystemExit("Usage: python3 scripts/pre_estimate_design.py v1|v2")
version = sys.argv[1]
path = root / ".env"
source = path.read_text() if path.exists() else ""
line = f"PRE_ESTIMATE_DESIGN={version}"
if re.search(r"^PRE_ESTIMATE_DESIGN=.*$", source, re.M):
    source = re.sub(r"^PRE_ESTIMATE_DESIGN=.*$", line, source, flags=re.M)
else:
    source = source.rstrip("\n") + "\n" + line + "\n"
path.write_text(source)
print(f"Local Pre-Estimate design: {version.upper()}")
print("Restart the local app: npm run stop, then npm run dev.")
