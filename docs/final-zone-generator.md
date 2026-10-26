# Final Estimate zone slides (local implementation)

The Final PDF order is shared title → ordered zones and their continuations →
investment summary → exactly 13 original corporate pages. The personal Project
Overview page is omitted as requested. Legacy cover selections remain stored;
the Builder no longer offers selecting a photo for that unused page.

## Assets and layout

`apps/backend/assets/proposals/zone-template-original.png` is the untouched user
background. `zone-design-reference.png` is the supplied visual reference. The
clean derivative removes the baked caption, four table rules, and Total band by
localized vertical background interpolation. The manifest records source and
output checksums and affected regions. No generative imaging was used.

`final_zone_layout.py` draws native Montserrat text, lines, prices, zone indices,
and gold Total bands on a strict 1440 × 810 canvas. Corporate pages are cloned
without rasterization by the existing Final PDF assembly service.

- Only 0–4 photos per zone are supported. Both the existing upload API and the
  Final renderer reject a fifth image; images are never silently discarded.
- Photos retain their aspect ratio, EXIF orientation, resolution, and alpha.
  Layouts: text-first / hero / adaptive pair / primary + two / strict 2 × 2.
- Continuations reuse that zone's photographs for visual context, show the same
  zone index and page fraction, and print the whole-zone total only at the end.
- Rows paginate by measured text height, with up to eight rows on a page.
  Text-only columns balance by height. Long names remain complete.
- Normal title words stay together; very long titles use wider compact layouts.
  Pathological names receive readable title continuations rather than clipping.
- Item names and saved extended amounts appear. No SKU/material codes,
  descriptions, notes, or quantity/unit-price detail appears on zone slides.
  Original descriptions and notes stay in the database for a future scope section.

## Prices and diagnostics

`final_pricing.py` reads saved amounts without calling the rule engine or writing
prices. Existing markup and discount apply once. Deterministic cent allocation
makes displayed item, zone, and project amounts reconcile. A manual project total
gets a separate summary adjustment instead of changing saved component amounts.

`GET /api/v1/pdf/{id}/final-check` supplies read-only diagnostics. The Builder and
preview display warnings in EN/RU; invalid totals, missing names, damaged photos,
or over-limit media block export with an actionable error. The Final renderer
also validates directly, including callers outside the Builder. Corporate asset
failures still stop generation. Preview and Download share the existing Blob
loader and renderer. The presentation itself always remains English.

The approved Pre generators, Price Book, rule engine, models, client records,
Excel service and workbook template were not changed.

## Persisted QA fixture

`WallPanels QA — 10 Zones Presentation Test`:

- Pre: `0dccb5f6-e25f-4844-b31f-d86468223a86`
- Final: `8962041e-7b3c-4aa3-a648-2c9da69d4502`
- 10 zones, 61 items, 20 original website images copied from `~/Desktop/photo wp`.
- Photo counts: 1, 2, 0, 3, 4, 1, 2, 0, **4**, 3. Zone 9 follows the later
  instruction limiting every zone to four photos.
- Rates reference the current Price Book where possible. Manually entered
  service amounts are explicitly marked as QA demo values in item descriptions.
  This is not a real client quotation and no rates were added to the Price Book.
- Control PDFs, native renders, XLSX workbooks, checks and source hashes live in
  `.local/qa/zone-generator/`. No browser download was initiated.

QA checks cover retained data after restart, Pre/Final independence, original
customer snapshots, untouched Price Book and original photo hashes, rejected
fifth uploads, all component names, totals, corporate page signatures and order,
uniform format, equal Preview/Download bytes and unchanged Excel cells/formulas.
Chrome desktop checks covered EN/RU at 1280, 1440, and the default 1512 px,
including four-photo controls and both previews. No horizontal page overflow was
observed at 1440 px and the console error check was clear. Temporary viewport
overrides were reset. Reverted QA edit flags were cleared so the fixture Final
remains a clean inherited copy.

Tests also cover 0–30 rows, long/unbroken names, 0–4 mixed image ratios, missing
assets, manual totals, cent allocation, zero amounts and unpriced scope.

## Rollback

The previous working source and complete local database snapshot are in
`.local/backups/pricebook-20261025T215506/`.
`change-files.json` records exactly this task's changed/new feature files.

Source rollback (dry run first):

```sh
.venv/bin/python scripts/pricebook_backup.py --restore-source .local/backups/pricebook-20261025T215506
.venv/bin/python scripts/pricebook_backup.py --restore-source .local/backups/pricebook-20261025T215506 --apply
npm run build
npm run stop
npm run dev
```

Source rollback leaves database records and uploaded media intact. No database
rollback is needed for this task; do not restore the full database over later
customer work. PostgreSQL is shared locally and must remain running.
