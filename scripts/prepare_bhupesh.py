"""Prepare the explicitly supplied BHUPESH case in an already backed-up local DB.
Uses existing API models; never resets a database or changes Price Book.
Usage: .venv/bin/python scripts/prepare_bhupesh.py /absolute/path/to/reference.png
"""

import argparse, json
from pathlib import Path
from decimal import Decimal
import httpx
from qa_credentials import qa_credentials

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("photo", type=Path)
args = parser.parse_args()
if not args.photo.is_file():
    parser.error("The supplied reference image is missing.")
backup_file = ROOT / ".local/qa/bhupesh-backup-path.txt"
if (
    not backup_file.exists()
    or not (Path(backup_file.read_text()) / "database.dump").exists()
):
    parser.error("Back up the local DB and storage first.")
c = httpx.Client(base_url="http://127.0.0.1:8010/api/v1", trust_env=False, timeout=60)
email, password = qa_credentials()
r = c.post(
    "/auth/login",
    json={"email": email, "password": password},
)
r.raise_for_status()
c.headers["Authorization"] = "Bearer " + r.json()["access_token"]


def call(method, path, **kw):
    r = c.request(method, path, **kw)
    r.raise_for_status()
    return r.json() if r.content else None


known = {
    "27d2c358-4233-478c-96a9-1a77be7ecc14",
    "23a0b8a0-c06a-4911-8562-5cf65b41efec",
    "2a006b0b-46d6-4b36-a6b4-1878727db66e",
}
active = call("GET", "/estimates")
unknown = [e for e in active if e["id"] not in known and e["client_name"] != "BHUPESH"]
if unknown:
    raise SystemExit(
        "Unknown records found. Preserve them and prepare an isolated local QA DB instead."
    )
existing = [e for e in active if e["client_name"] == "BHUPESH"]
if existing:
    raise SystemExit(
        "BHUPESH already exists. Verify it rather than creating a duplicate."
    )
fixture = json.loads((ROOT / "tests/fixtures/bhupesh.json").read_text())
est = call("POST", "/estimates", json=fixture["estimate"])
eid = est["id"]
call("PATCH", f"/estimates/{eid}", json={"markup_pct": 0, "discount_pct": 0})
keys = [
    "name",
    "description",
    "section",
    "calc_type",
    "quantity",
    "unit",
    "unit_price",
    "total_price",
    "is_tbd",
]
for n, scope in enumerate(fixture["zones"]):
    data = {k: v for k, v in scope.items() if k not in ("items", "expected_total")}
    data["sort_order"] = n
    if n == 0:
        z = call("PATCH", f'/estimates/{eid}/zones/{est["zones"][0]["id"]}', json=data)
    else:
        z = call("POST", f"/estimates/{eid}/zones", json=data)
    for i, row in enumerate(scope["items"]):
        call(
            "POST",
            f"/estimates/{eid}/line-items",
            json={**dict(zip(keys, row)), "zone_id": z["id"], "sort_order": i},
        )
    call(
        "POST",
        f'/estimates/{eid}/zones/{z["id"]}/images/1',
        files={
            "file": (
                "BHUPESH - shared project reference.png",
                args.photo.read_bytes(),
                "image/png",
            )
        },
    )
est = call("GET", f"/estimates/{eid}")
assert (
    Decimal(est["subtotal"]) == Decimal("89300")
    and est["type"] == "final"
    and len(est["zones"]) == 5
)
for z, source in zip(est["zones"], fixture["zones"]):
    assert Decimal(z["subtotal"]) == Decimal(source["expected_total"]) and len(
        z["line_items"]
    ) == len(source["items"])
for e in active:
    if e["id"] in known:
        call("DELETE", "/estimates/" + e["id"])
(ROOT / ".local/qa/bhupesh-id.txt").write_text(eid)
(ROOT / ".local/qa/bhupesh-created.json").write_text(json.dumps(est, indent=2))
print(
    json.dumps(
        {
            "id": eid,
            "url": f"http://localhost:5190/estimates/{eid}",
            "zones": len(est["zones"]),
            "items": sum(len(z["line_items"]) for z in est["zones"]),
            "total": est["subtotal"],
        },
        indent=2,
    )
)
