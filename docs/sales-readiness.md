# Staff review readiness — 27 October 2026

Scope: only the new corporate `estimate-platform-new` repository and the
`WallPanels Estimate Platform New` Railway project. Existing production and
personal infrastructure were not changed.

## Review projects

All four started as Pre-estimates. Staff may change their names and data.

| Client/project | Zones | Components | Photos | Estimate ID |
| --- | ---: | ---: | ---: | --- |
| Bennett — 184 Harbor Drive | 4 | 11 | 10 | e13485bb-580e-4c8e-927a-11b8e137fae8 |
| Morgan — 72 Palm Grove Court | 5 | 18 | 12 | 8b969a05-f6b0-463f-b4c0-c53ec12a6439 |
| Sullivan — 315 Magnolia Avenue | 10 | 38 | 27 | 2c335e5a-155e-49cb-839e-f1c93bb9fe56 |
| Anderson — 608 Ocean Crest Lane | 12 | 53 | 30 | a6983c7c-9eda-4486-b658-a46bd37d8be3 |

Photos came from the supplied desktop `photo wp` folder. Each zone has 1–4 photos,
including portrait and landscape examples. Final presentations use the selected
zone photo and repeat it on continuation pages. The 12-zone Investment Summary
is balanced 6 + 6 across two pages, with Grand Total on the last page.

## Verified behavior and fixes

- Shared login/access for all seven User accounts; saved author/history records,
  conflict protection, and cross-account changes.
- Price Book editing and quotation, calculator totals, fixed mirror installation
  fee preserved when measured material quantity changes.
- Quick Estimate keeps its separate formulas but reads applicable saved rates.
  Quick PDFs use the preliminary path and do not require Final-only photos.
- Estimate/zone copies preserve photos, selections, prices and adjustments.
- Pre changes propagate to unmodified Final fields; Final overrides do not change Pre.
- Pre/Final Preview and Download match byte for byte. Final retains all 13 native
  corporate pages. PDF pages were visually inspected without changing approved design.
- XLSX rows and Grand Total reconcile with saved quantities, prices, markup,
  discount and manual adjustments. Saved XLSX versions remain immutable.
- AI actions remain disabled while no API key is configured.

The fixture verification covered 150 API checks; separate disposable-project
checks covered 88 pricing, persistence, copy and branch cases. Temporary QA
projects/catalogue entries were archived. The backend suite passed 99 tests
with one optional local fixture skipped; focused PDF-retention, delivery and
backup tests also passed. Frontend production build passed.

## PDF storage policy

Owner explicitly changed the requirement: presentations are generated only for
Preview/Download, not retained as PDF versions or included in data backups.
PDF save requests are rejected, and old saved-PDF links direct users to regenerate.
Estimate data, photos, history, users, prices and XLSX remain persistent.
The corporate source PDF remains a release asset in Git/the application image.

Cleanup removed 19 generated PDFs (554,285,527 bytes) from the application disk.
Three existing backup archives were rewritten and checksum-verified, shrinking
from 519,088,198 to 12,016,490 bytes in total. A fresh 12,117,213-byte backup passed
download verification and restoration into an isolated temporary database.
Application disk usage subsequently measured approximately 0.035 GB, down from
0.592 GB. No disk resize was performed.

Operational procedure and recovery boundaries: [Railway operations](railway-operations.md).
