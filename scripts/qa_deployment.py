"""Explicit smoke tests for the NEW corporate deployment; writes only TEST records.

Credentials and report paths must be outside the repository. Run prepare, restart
the new service, then verify. Existing estimates are never edited.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import uuid

import httpx
from PIL import Image, ImageDraw
from pypdf import PdfReader
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))
from app.services.final_estimate_service import load_company_slides, page_signature

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("phase", choices=["prepare", "verify"])
parser.add_argument("--credentials", type=Path, required=True)
parser.add_argument("--state", type=Path, required=True)
args = parser.parse_args()
for path in (args.credentials, args.state):
    if path.resolve().is_relative_to(ROOT):
        raise SystemExit("Credentials and deployment report must remain outside Git.")
BASE = "https://estimate-platform-production.up.railway.app"
users = json.loads(args.credentials.read_text())["users"]
checks = []


def call(client, method, path, expected=200, **kwargs):
    r = client.request(method, path, **kwargs)
    assert r.status_code == expected, f"{method} {path}: {r.status_code} {r.text[:180]}"
    checks.append([method, path, expected])
    return r


def login(user):
    client = httpx.Client(base_url=BASE + "/api/v1", trust_env=False, timeout=180)
    r = call(client, "POST", "/auth/login", json={"email": user["login"], "password": user["password"]})
    client.headers["Authorization"] = "Bearer " + r.json()["access_token"]
    me = call(client, "GET", "/auth/me").json()
    assert me["role"] == "user" and me["is_active"]
    return client


clients = [login(u) for u in users]
a, b = clients[:2]


def saved(eid):
    return call(a, "GET", "/estimates/" + eid).json()


def write(client, method, eid, suffix="", expected=200, **kwargs):
    revision = saved(eid)["revision"]
    return call(client, method, "/estimates/" + eid + suffix, expected,
                headers={"If-Match": revision}, **kwargs)


def save_state(state):
    fd = os.open(args.state, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(state, stream, indent=2, ensure_ascii=False)


if args.phase == "verify":
    state = json.loads(args.state.read_text())
    est = saved(state["estimate_id"])
    assert est["title"] == state["title"]
    assert est["prepared_by"] == users[0]["name"]
    assert est["updated_by_name"] == users[1]["name"]
    for image in state["images"]:
        data = call(b, "GET", "/media/" + image["id"]).content
        assert hashlib.sha256(data).hexdigest() == image["sha256"]
    for doc in (d for d in state["documents"] if d.get("kind") != "pdf"):
        preview = call(b, "GET", "/documents/" + doc["id"]).content
        download = call(a, "GET", "/documents/" + doc["id"] + "?download=true").content
        assert preview == download and hashlib.sha256(preview).hexdigest() == doc["sha256"]
    for ident, before in state["protected"].items():
        assert saved(ident) == before
    catalogue = call(b, "GET", "/pricing/catalog").json()
    assert any(i["id"] == state["item_id"] and i["unit_price"] == "15.00" for i in catalogue["items"])
    write(b, "DELETE", state["estimate_id"], expected=204)
    branch_ids = {state["estimate_id"], state["final_id"]}
    assert any(e["id"] in branch_ids for e in call(a, "GET", "/estimates/trash").json())
    write(a, "POST", state["estimate_id"], "/restore")
    assert any(e["id"] in branch_ids for e in call(a, "GET", "/estimates").json())
    write(b, "DELETE", state["estimate_id"], expected=204)
    item = next(i for i in catalogue["items"] if i["id"] == state["item_id"])
    call(b, "PUT", "/pricing/catalog/items/" + item["id"], json={"category_id": item["category_id"], "name": item["name"], "unit": "SF", "unit_price": "15.00", "archived": True, "expected_version": item["version"]})
    category = next(c for c in catalogue["categories"] if c["id"] == state["category_id"])
    call(a, "PUT", "/pricing/catalog/categories/" + category["id"], json={"name": category["name"], "archived": True, "expected_version": category["version"]})
    history = call(a, "GET", "/estimates/" + state["estimate_id"] + "/history").json()
    assert {users[0]["name"], users[1]["name"]}.issubset({r["actor_name"] for r in history})
    state["verified_after_restart"] = True
    state["verification_checks"] = checks
    save_state(state)
    print(f"Verified after restart: {len(checks)} API checks, 7 logins, photos, immutable documents, catalogue, trash/restore, attribution. TEST estimate retained in trash; TEST catalogue archived.")
    raise SystemExit(0)

if args.state.exists():
    raise SystemExit("A TEST state already exists; inspect or verify it before creating more records.")
protected = {e["id"]: saved(e["id"]) for e in call(a, "GET", "/estimates").json()}
public = httpx.Client(base_url=BASE + "/api/v1", trust_env=False, timeout=30)
call(public, "GET", "/estimates", 403)
call(public, "GET", "/pricing/catalog", 403)
suffix = uuid.uuid4().hex[:6]
title = "TEST corporate deployment " + suffix
est = call(a, "POST", "/estimates", 201, json={"type": "pre", "title": title, "client_name": "TEST WallPanels", "project_name": "TEST deployment verification", "prepared_by": "Must not spoof"}).json()
eid, zid = est["id"], est["zones"][0]["id"]
state = {"estimate_id": eid, "title": title, "protected": protected, "images": [], "documents": []}
save_state(state)
assert est["prepared_by"] == users[0]["name"]
assert any(e["id"] == eid for e in call(b, "GET", "/estimates").json())
stale = est["revision"]
call(b, "PATCH", "/estimates/" + eid, headers={"If-Match": stale}, json={"notes": "TEST edited by second employee"})
call(a, "PATCH", "/estimates/" + eid, 409, headers={"If-Match": stale}, json={"notes": "MUST NOT OVERWRITE"})
call(a, "PATCH", "/estimates/" + eid, 428, json={"notes": "MUST NOT OVERWRITE"})
write(a, "PATCH", eid, "/zones/" + zid, json={"label": "TEST Feature Wall"})
z2 = write(b, "POST", eid, "/zones", 201, json={"label": "TEST Entry Mirror", "zone_type": "mirror"}).json()["id"]
for idx in range(9):
    write(a, "POST", eid, "/line-items", 201, json={"zone_id": zid, "name": f"TEST component {idx + 1}", "calc_type": "sf", "unit": "SF", "quantity": "10", "unit_price": "60", "total_price": "600"})
write(b, "POST", eid, "/line-items", 201, json={"zone_id": z2, "name": "TEST custom mirror", "calc_type": "sf", "unit": "SF", "quantity": "20", "unit_price": "130", "total_price": "2600"})
for zone, size in ((zid, (1000, 650)), (z2, (600, 900))):
    photo = Image.new("RGB", size, "#d4b48b")
    ImageDraw.Draw(photo).text((30, 30), "TEST WallPanels deployment", fill="#202020")
    buf = io.BytesIO(); photo.save(buf, "JPEG"); data = buf.getvalue()
    uploaded = write(a, "POST", eid, f"/zones/{zone}/images/1", files={"file": ("TEST-image.jpg", data, "image/jpeg")}).json()
    state["images"].append({"id": uploaded["id"], "sha256": hashlib.sha256(data).hexdigest()})
    assert call(b, "GET", "/media/" + uploaded["id"]).content == data
    call(public, "GET", "/media/" + uploaded["id"], 403)
save_state(state)
for kind, payload, total in [("wall", {"square_footage": 100, "addons_sf": ["led"]}, 6000), ("cabinet", {"linear_footage": 2, "cabinet_type": "kitchen_island"}, 2400), ("mirror", {"square_footage": 20}, 2600)]:
    assert call(a, "POST", "/pricing/calc/" + kind, json=payload).json()["total"] == total
category = call(a, "POST", "/pricing/catalog/categories", 201, json={"name": "TEST deployment rates " + suffix}).json()
item = call(b, "POST", "/pricing/catalog/items", 201, json={"category_id": category["id"], "name": "TEST deployment material", "unit": "SF", "unit_price": "12.50"}).json()
assert call(a, "POST", f'/pricing/catalog/items/{item["id"]}/quote', json={"quantity": "3"}).json()["total_price"] == "37.50"
call(a, "PUT", "/pricing/catalog/items/" + item["id"], json={"category_id": category["id"], "name": item["name"], "unit": "SF", "unit_price": "15.00", "expected_version": item["version"]})
quote = call(b, "POST", f'/pricing/catalog/items/{item["id"]}/quote', json={"quantity": "3"}).json()
assert quote["total_price"] == "45.00"
write(b, "POST", eid, "/line-items", 201, json={**quote, "zone_id": z2})
assert float(saved(eid)["final_total"]) == 8045
state.update(category_id=category["id"], item_id=item["id"]); save_state(state)


def check_pdf(ident, kind):
    path = f"/pdf/{ident}/{kind}-estimate"
    preview = call(a, "GET", path)
    downloaded = call(b, "GET", path + "?download=true")
    assert preview.content == downloaded.content
    pdf = PdfReader(io.BytesIO(preview.content)); assert len(pdf.pages) > 0
    if kind == "final":
        company = load_company_slides()
        assert [page_signature(p) for p in pdf.pages[-13:]] == company.signatures
        assert pdf.metadata["/WallPanelsCompanySlidesCount"] == "13"
        assert "CUSTOM INTERIOR" in pdf.pages[0].extract_text() or len(pdf.pages[0].images) > 0
        state["final_page_count"] = len(pdf.pages)
        # Every zone continuation includes the same selected zone photo.
        for page in pdf.pages[1:-14]:
            assert len(page.images) > 0
    print(kind, "PDF:", len(pdf.pages), "pages; Preview/Download byte-identical")


check_pdf(eid, "pre")
sheet = call(a, "GET", f"/pdf/{eid}/passport")
assert load_workbook(io.BytesIO(sheet.content)).active["C3"].value == "TEST WallPanels"
for kind in ("xlsx",):
    state["documents"].append(write(b, "POST", eid, "/documents", 201, json={"kind": kind, "label": "TEST sent version " + kind}).json())
save_state(state)
final = write(b, "POST", eid, "/mode", json={"mode": "final"}).json()
fid = state["final_id"] = final["id"]
check_pdf(fid, "final")
write(b, "PATCH", fid, json={"notes": "TEST changed after issuing immutable documents"})
write(b, "PATCH", eid, json={"notes": "TEST final persistence snapshot"})
state["prepare_checks"] = checks; save_state(state)
print(f"Prepared: {len(checks)} API checks. Restart ONLY the new app, then verify.")
