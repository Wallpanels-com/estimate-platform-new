# Corporate deployment verification — 27 October 2026

Application release: `b7907980f9fee91b7ac5d8f769f532036cb93401`.
Repository: `Wallpanels-com/estimate-platform-new`, branch `main`.
Project: `76fff733-80e1-436c-8670-4f2d3e4fbd1f`, Wallpanels.com workspace.
Public HTTPS: https://estimate-platform-production.up.railway.app

## Completed

- Seven active employee logins: dmitry, katya1, igor, masha, anton, kit, katya2.
  Each has exactly the same User permissions. Passwords remain bcrypt hashes in
  PostgreSQL; temporary credentials are in an owner-readable local file outside Git.
- 82 preparation API checks and 35 verification checks after application replacement.
  The 35 verification checks were repeated after a separate in-place app restart.
- Shared Estimate creation and editing by two different employees; Prepared by
  cannot be spoofed, and history contains both authors. Stale writes return 409;
  missing revision tokens return 428.
- Wall, Cabinetry and Mirror reference calculations: $6,000, $2,400 and $2,600.
  Catalogue rate creation, editing, cross-account quotes and adding the quote to
  an Estimate produce the expected $8,045 test total.
- Two zone photos (landscape and portrait), authenticated access and byte checks
  after restart. Final zone continuation pages contain images.
- Pre PDF: 7 pages; Final PDF: 18 pages, including exactly 13 corporate pages in
  their original order verified against native page signatures. Preview and
  Download are byte-identical for both modes.
- XLSX opens in openpyxl and contains the saved client name. Three immutable
  saved versions (Pre PDF, Final PDF, XLSX) retain their hashes after subsequent
  edits, redeployment and restart.
- Trash and restore work across accounts. TEST catalogue entries are archived;
  the TEST estimate remains recoverable in Trash. No existing customer record
  was edited by the deployment smoke test.
- Frontend production build, translation tests, 27 original Quick Estimate
  parity fixtures, PDF source/wiring tests and repository checks pass. Backend
  PDF/layout/pricing regression tests pass (one optional legacy local backup
  fixture is skipped when absent); new collaboration and backup safety tests pass.
- In-app browser: login, desktop Builder, photographs, Team accounts and Russian
  Price Book load; no console errors/warnings on the checked final screen.
  Personal Chrome was excluded after the owner's instruction.
- Both Railway services are online. PostgreSQL has no public TCP proxy.
  Application files are mounted on `estimate-files` at `/data`.

## Backup proof

Private bucket: `estimate-backups` in the same new project. Daily logical/file
backups run in the single application replica; no personal account is involved.

The first automatic archive was uploaded and read back successfully. A second
archive (`13764ec831bd48068a048f71bc666b4d`) was also restored into a new temporary
database using PostgreSQL 18 tools. Every table count and the migration revision
matched; that verification database alone was then removed.

The verified archive contains 23 files and approximately 91.5 MB: native database
dump, referenced photographs and immutable exports, templates and corporate assets.
All individual file hashes match after downloading the archive from the bucket.
Completed backup metadata survives application restart on `/data/operations`.

## Explicit limitations

- Local estimates/custom local Price Book content have not been migrated to the
  new empty corporate database automatically. Local data remains intact.
- Optional AI extraction needs an approved corporate `OPENAI_API_KEY`.
- Backups are daily logical snapshots, not continuous PITR. They run when the
  app is available; a stopped app catches up on its next startup. No automatic
  backup deletion is enabled until retention is agreed.
- Railway native volume backup schedules were not configured; the implemented
  independent private bucket backups provide the tested recovery path.

Operational instructions are in [Railway operations](railway-operations.md).
