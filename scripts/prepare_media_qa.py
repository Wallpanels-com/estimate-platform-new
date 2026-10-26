"""Create the explicitly requested local-only ten-zone PDF media fixture.

Only adds its own clearly named QA estimate through localhost APIs. No downloads
of PDF, no changes to BHUPESH, pricing, schema, or existing uploaded images.
"""

import asyncio
from datetime import date
from pathlib import Path
from decimal import Decimal
import json
import hashlib
import shutil
import httpx
from PIL import Image
from qa_credentials import qa_credentials

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "tests/fixtures/pdf-media"
OUT = ROOT / ".local/qa/pdf-media"
TITLE = "QA - PDF Image Variations (10 zones)"
CLIENT = "Interior Project"
PHOTO_SIZES = [
    (1200, 750),
    (700, 1100),
    (900, 900),
    (1280, 720),
    (720, 1080),
    (1200, 800),
    (800, 800),
    (650, 1000),
    (1200, 700),
    (700, 1050),
    (850, 850),
    (320, 180),
    (2200, 300),
]


async def photos():
    ASSETS.mkdir(parents=True, exist_ok=True)
    limit = asyncio.Semaphore(4)
    manifest = []
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=25, trust_env=False
    ) as client:

        async def fetch(n, size):
            path = ASSETS / f"photo-{n+1:02d}.jpg"
            url = f"https://picsum.photos/seed/wallpanels-media-qa-{n+1}/{size[0]}/{size[1]}.jpg"
            async with limit:
                if not path.exists():
                    response = await client.get(url)
                    response.raise_for_status()
                    path.write_bytes(response.content)
                with Image.open(path) as im:
                    assert im.size == size
                manifest.append(
                    {
                        "name": path.name,
                        "source": url,
                        "size": size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )

        await asyncio.gather(*(fetch(n, size) for n, size in enumerate(PHOTO_SIZES)))
    drawing = ASSETS / "architectural-reference.png"
    shutil.copy2(ROOT / "tests/fixtures/bhupesh-reference.png", drawing)
    manifest.append(
        {
            "name": drawing.name,
            "source": "User-provided architectural reference (unaltered copy)",
            "size": [829, 372],
            "sha256": hashlib.sha256(drawing.read_bytes()).hexdigest(),
        }
    )
    (ASSETS / "sources.json").write_text(
        json.dumps(sorted(manifest, key=lambda x: x["name"]), indent=2)
    )
    return [ASSETS / f"photo-{n+1:02d}.jpg" for n in range(len(PHOTO_SIZES))], drawing


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    photo, drawing = asyncio.run(photos())
    definitions = [
        ("Living Room - Landscape", [photo[0]], 3),
        ("Staircase - Portrait", [photo[1]], 3),
        ("Library - Square Reference", [photo[2]], 3),
        ("Lounge - Two References", photo[3:5], 4),
        ("Dining Room - Three References", photo[5:8], 4),
        ("Studio - Four References & Low Resolution", photo[8:12], 3),
        ("Hallway - No Photo / Pricing Pending", [], 1),
        ("Feature Wall - Architectural Drawing", [drawing], 4),
        ("Cabinetry and Wall Finishes - No Photo", [], 3),
        ("Terrace - Wide Panoramic Reference", [photo[12]], 3),
    ]
    with httpx.Client(
        base_url="http://127.0.0.1:8010/api/v1", trust_env=False, timeout=30
    ) as c:
        email, password = qa_credentials()
        response = c.post(
            "/auth/login",
            json={"email": email, "password": password},
        )
        response.raise_for_status()
        c.headers["Authorization"] = "Bearer " + response.json()["access_token"]

        def call(method, path, **kw):
            response = c.request(method, path, **kw)
            response.raise_for_status()
            return response.json() if response.content else None

        active = call("GET", "/estimates")
        existing = [e for e in active if e["title"] == TITLE]
        if existing:
            print(
                "Fixture already exists:",
                f'http://localhost:5190/estimates/{existing[0]["id"]}',
            )
            return
        protected = {e["id"]: call("GET", "/estimates/" + e["id"]) for e in active}
        (OUT / "existing-estimates-before.json").write_text(
            json.dumps(protected, indent=2)
        )
        (OUT / "pricing-before.json").write_text(
            json.dumps(call("GET", "/pricing/config"), sort_keys=True)
        )
        est = call(
            "POST",
            "/estimates",
            json={
                "type": "pre",
                "title": TITLE,
                "client_name": CLIENT,
                "project_name": "Local photo and layout review",
                "prepared_by": "WallPanels QA",
                "estimate_date": date.today().isoformat(),
                "description": "Separate local QA fixture: image counts, aspect ratios, long scope and pagination. Not a client estimate.",
            },
        )
        eid = est["id"]
        (OUT / "estimate-id.txt").write_text(eid)
        summary = []
        for n, (label, images, count) in enumerate(definitions):
            data = {
                "label": label,
                "sort_order": n,
                "zone_type": "wall",
                "notes": "Local media-layout QA fixture only.",
            }
            if n == 0:
                z = call(
                    "PATCH",
                    f'/estimates/{eid}/zones/{est["zones"][0]["id"]}',
                    json=data,
                )
            else:
                z = call("POST", f"/estimates/{eid}/zones", json=data)
            for k in range(count):
                pending = n == 6
                section = "General"
                name = [
                    "Wall panel installation",
                    "Custom cabinetry",
                    "LED profile and lighting",
                    "Mirror delivery and installation",
                    "Finishing and alignment",
                ][k % 5]
                description = "Site measured"
                if n == 8:
                    name = [
                        "Cabinet fronts and concealed access",
                        "Panel installation and corner detailing",
                        "Integrated lighting profiles",
                    ][k]
                    description = [
                        "Aligned panels with service access.",
                        "Coordinated joints and corner finish.",
                        "Continuous lighting with hidden wiring.",
                    ][k]
                if n == 5 and k == 0:
                    description = "Site measured"
                qty = 8 + k
                rate = 75 if k % 2 == 0 else 120
                item = {
                    "zone_id": z["id"],
                    "sort_order": k,
                    "section": section,
                    "name": name,
                    "description": description,
                    "calc_type": "manual",
                    "quantity": qty,
                    "unit": "SF",
                    "unit_price": None if pending else rate,
                    "total_price": 0 if pending else qty * rate,
                    "is_tbd": pending,
                }
                call("POST", f"/estimates/{eid}/line-items", json=item)
            for slot, path in enumerate(images, 1):
                mime = "image/png" if path.suffix == ".png" else "image/jpeg"
                call(
                    "POST",
                    f'/estimates/{eid}/zones/{z["id"]}/images/{slot}',
                    files={"file": (path.name, path.read_bytes(), mime)},
                )
            summary.append({"label": label, "photos": len(images), "line_items": count})
        result = call("GET", f"/estimates/{eid}")
        assert len(result["zones"]) == 10
        assert [len(z["images"]) for z in result["zones"]] == [
            len(x[1]) for x in definitions
        ]
        assert sum(len(z["line_items"]) for z in result["zones"]) == 31
        for original_id, before in protected.items():
            assert (
                call("GET", "/estimates/" + original_id) == before
            ), "Existing estimate changed"
        assert call("GET", "/pricing/config") == json.loads(
            (OUT / "pricing-before.json").read_text()
        )
        (OUT / "estimate.json").write_text(json.dumps(result, indent=2))
        report = {
            "id": eid,
            "url": f"http://localhost:5190/estimates/{eid}",
            "zones": summary,
            "items": 31,
            "images": 14,
            "total": result["final_total"],
            "existing_estimates_unchanged": True,
            "pdf_downloads": 0,
        }
        (OUT / "fixture-report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    prepare()
