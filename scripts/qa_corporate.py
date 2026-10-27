"""Loopback-only equal-User access and persistence checks; no cloud writes."""
import argparse
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import secrets
import uuid
import httpx
from PIL import Image
from pypdf import PdfReader
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".local/qa/corporate"
OUT.mkdir(parents=True, exist_ok=True)
checks = []


def call(client, method, path, expected=200, **kwargs):
    response = client.request(method, path, **kwargs)
    assert response.status_code == expected, f"{method} {path}: {response.status_code} {response.text[:250]}"
    checks.append([method, path, expected])
    return response


def login(email, password):
    client = httpx.Client(base_url="http://127.0.0.1:8010/api/v1", trust_env=False, timeout=120)
    result = call(client, "POST", "/auth/login", json={"email": email, "password": password}).json()
    client.headers["Authorization"] = "Bearer " + result["access_token"]
    return client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["prepare", "verify"])
    phase = parser.parse_args().phase
    owner = json.loads((ROOT / ".local/employee-access.json").read_text())[0]
    admin = login(owner["email"], owner["password"])
    statefile = OUT / "state.json"
    if phase == "verify":
        state = json.loads(statefile.read_text())
        sales = login(state["sales_email"], state["sales_password"])
        assert call(sales, "GET", "/auth/me").json()["role"] == "user"
        assert all(row["role"] == "user" for row in call(sales, "GET", "/users").json())
        estimate = call(sales, "GET", "/estimates/" + state["estimate_id"]).json()
        assert estimate["prepared_by"] == "Corporate QA Sales A"
        assert estimate["updated_by_name"] == "Corporate QA Sales B"
        assert estimate["title"] == "Corporate QA edited by second employee"
        current_catalog = call(admin, "GET", "/pricing/catalog").json()
        for group in ("categories", "items"):
            assert all(entry in current_catalog[group] for entry in state["catalog_after"][group])
        media = call(sales, "GET", "/media/" + state["image_id"])
        assert hashlib.sha256(media.content).hexdigest() == state["photo_sha256"]
        for doc in (d for d in state["documents"] if d.get("kind") != "pdf"):
            preview = call(sales, "GET", "/documents/" + doc["id"])
            downloaded = call(sales, "GET", "/documents/" + doc["id"] + "?download=true")
            assert preview.content == downloaded.content
            assert hashlib.sha256(preview.content).hexdigest() == doc["sha256"]
        for ident, before in state["protected_estimates"].items():
            assert call(admin, "GET", "/estimates/" + ident).json() == before
        history = call(sales, "GET", f'/estimates/{state["estimate_id"]}/history').json()
        assert any(row["actor_name"] == "Corporate QA Sales A" for row in history)
        assert any(row["actor_name"] == "Corporate QA Sales B" for row in history)
        assert "password_hash" not in json.dumps(history)
        # Both employees can edit the same catalogue; no privileged role exists.
        category = call(sales, "POST", "/pricing/catalog/categories", 201, json={"name": "Corporate QA shared permissions " + uuid.uuid4().hex[:8]}).json()
        item = call(sales, "POST", "/pricing/catalog/items", 201, json={"category_id": category["id"], "name": "Shared work", "unit": "SF", "unit_price": "12.50"}).json()
        quote = call(admin, "POST", f'/pricing/catalog/items/{item["id"]}/quote', json={"quantity": "3"}).json()
        assert quote["total_price"] == "37.50"
        edited = call(admin, "PUT", "/pricing/catalog/items/" + item["id"], json={"category_id": category["id"], "name": "Shared work updated", "unit": "SF", "unit_price": "15.00", "expected_version": item["version"]}).json()
        assert call(sales, "POST", f'/pricing/catalog/items/{item["id"]}/quote', json={"quantity": "3"}).json()["total_price"] == "45.00"
        call(sales, "PUT", "/pricing/catalog/items/" + item["id"], json={"category_id": category["id"], "name": edited["name"], "unit": "SF", "unit_price": "15.00", "archived": True, "expected_version": edited["version"]})
        call(admin, "PUT", "/pricing/catalog/categories/" + category["id"], json={"name": category["name"], "archived": True, "expected_version": category["version"]})
        call(sales, "DELETE", "/estimates/" + state["estimate_id"], 204)
        assert any(row["title"] == "Corporate QA edited by second employee" for row in call(admin, "GET", "/estimates/trash").json())
        call(admin, "POST", f'/estimates/{state["estimate_id"]}/restore')
        call(admin, "DELETE", "/estimates/" + state["estimate_id"], 204)
        for ident in state["user_ids"]:
            call(admin, "PATCH", "/users/" + ident, json={"is_active": False})
        call(sales, "GET", "/auth/me", 401)
        report = {"checks": len(checks), "restart_persistence": True, "issued_preview_download_identical": True,
                  "protected_existing_estimates_unchanged": True, "qa_estimate_in_trash": True,
                  "qa_users_disabled": True, "checks_detail": checks}
        (OUT / "results.json").write_text(json.dumps(report, indent=2))
        print(f"Corporate QA verified: {len(checks)} checks; equal User access, restart, photos, immutable documents and existing estimates preserved.")
        return
    if statefile.exists():
        raise SystemExit("QA state already exists; run verify or inspect it before creating another fixture.")
    suffix = uuid.uuid4().hex[:8]
    users = []
    for role, name in [("user", "Corporate QA Sales A"), ("user", "Corporate QA Sales B"), ("user", "Corporate QA Employee")]:
        email, password = f"corporate-{len(users)}-{suffix}@example.com", secrets.token_urlsafe(18)
        user = call(admin, "POST", "/users", 201, json={"name": name, "email": email, "password": password, "role": role}).json()
        users.append({**user, "password": password})
    a = login(users[0]["email"], users[0]["password"])
    b = login(users[1]["email"], users[1]["password"])
    protected = {row["id"]: call(admin, "GET", "/estimates/" + row["id"]).json() for row in call(admin, "GET", "/estimates").json()}
    before_catalog = call(admin, "GET", "/pricing/catalog").json()
    for method, path, body in [
        ("GET", "/users", None), ("POST", "/users", {"email": "denied@example.com", "password": secrets.token_urlsafe(18), "name": "Denied"}),
        ("POST", "/pricing/catalog/categories", {"name": "Denied"}),
        ("POST", "/pricing/catalog/items", {"category_id": "wall", "name": "Denied", "unit_price": "5"}),
        ("PUT", "/pricing/catalog/categories/wall", {"name": "Denied"}),
        ("PUT", "/pricing/catalog/items/unknown", {"category_id": "wall", "name": "Denied", "unit_price": "5"}),
        ("POST", "/pricing/config/reset", None), ("PUT", "/pricing/config", {"config": {}}), ("GET", "/audit", None),
    ]:
        # Anonymous callers are denied; the same employee can read shared resources.
        anonymous = httpx.Client(base_url="http://127.0.0.1:8010/api/v1", trust_env=False)
        call(anonymous, method, path, 403, **({"json": body} if body is not None else {}))
    assert call(admin, "GET", "/pricing/catalog").json() == before_catalog
    public = httpx.Client(base_url="http://127.0.0.1:8010", trust_env=False, timeout=30)
    call(public, "POST", "/api/v1/auth/register", 403, json={"email": "no-signup@example.com", "password": secrets.token_urlsafe(18)})
    est = call(a, "POST", "/estimates", 201, json={"type": "pre", "client_name": "Corporate QA", "title": "Corporate QA disposable", "prepared_by": "Cannot spoof"}).json()
    eid, zid = est["id"], est["zones"][0]["id"]
    assert est["prepared_by"] == users[0]["name"]
    assert any(row["id"] == eid for row in call(b, "GET", "/estimates").json())
    call(b, "PATCH", "/estimates/" + eid, json={"title": "Corporate QA edited by second employee"})
    item = call(a, "POST", f"/estimates/{eid}/line-items", 201, json={"zone_id": zid, "name": "Wall panel installation", "calc_type": "sf", "unit": "SF", "quantity": "10", "unit_price": "60", "total_price": "600"}).json()
    call(b, "PATCH", f'/estimates/{eid}/line-items/{item["id"]}', json={"quantity": "12"})
    photo = io.BytesIO(); Image.new("RGB", (800, 600), "#d4b48b").save(photo, format="JPEG")
    uploaded = call(a, "POST", f"/estimates/{eid}/zones/{zid}/images/1", files={"file": ("synthetic.jpg", photo.getvalue(), "image/jpeg")}).json()
    call(public, "GET", "/api/v1/media/" + uploaded["id"], 403)
    call(public, "GET", f'/storage/images/{eid}/{zid}/' + Path(uploaded["file_path"]).name, 404)
    assert call(b, "GET", "/media/" + uploaded["id"]).content == photo.getvalue()
    for kind, payload, total in [("wall", {"square_footage": 100, "addons_sf": ["led"]}, 6000), ("cabinet", {"linear_footage": 2, "cabinet_type": "kitchen_island"}, 2400), ("mirror", {"square_footage": 20}, 2600)]:
        assert call(a, "POST", "/pricing/calc/" + kind, json=payload).json()["total"] == total
    pre = call(b, "GET", f"/pdf/{eid}/pre-estimate")
    assert len(PdfReader(io.BytesIO(pre.content)).pages) > 0
    documents = [call(b, "POST", f"/estimates/{eid}/documents", 201, json={"kind": "xlsx", "label": "Passport sent version"}).json()]
    sheet = call(b, "GET", "/documents/" + documents[0]["id"])
    assert load_workbook(io.BytesIO(sheet.content)).active["C3"].value == "Corporate QA"
    final = call(b, "POST", f"/estimates/{eid}/mode", json={"mode": "final"}).json()
    result = call(b, "GET", f'/pdf/{final["id"]}/final-estimate')
    assert len(PdfReader(io.BytesIO(result.content)).pages) >= 16
    # A later saved change must never rewrite the issued PDF or XLSX.
    call(b, "PATCH", f'/estimates/{final["id"]}', json={"notes": "Edited after issuing"})
    call(a, "DELETE", f"/estimates/{eid}/permanent", 409)
    call(admin, "DELETE", f"/estimates/{eid}/permanent", 409)
    call(admin, "POST", f'/users/{users[0]["id"]}/password', 204, json={"password": secrets.token_urlsafe(18)})
    call(a, "GET", "/auth/me", 401)
    # Record editing attribution on the Pre branch after its line/photo writes.
    call(b, "PATCH", "/estimates/" + eid, json={"notes": "Final QA persistence snapshot"})
    state = {"estimate_id": eid, "image_id": uploaded["id"], "photo_sha256": hashlib.sha256(photo.getvalue()).hexdigest(),
             "sales_email": users[1]["email"], "sales_password": users[1]["password"], "user_ids": [user["id"] for user in users],
             "documents": documents, "catalog_after": call(admin, "GET", "/pricing/catalog").json(), "protected_estimates": protected,
             "checks_before_restart": checks}
    statefile.write_text(json.dumps(state, indent=2)); statefile.chmod(0o600)
    print(f"Corporate QA prepared: {len(checks)} checks. Restart app, then run verify.")


if __name__ == "__main__":
    main()
