# Corporate Railway deployment

Only the new corporate resources below are in scope. Existing projects and
personal infrastructure must not be edited.

- Workspace: Wallpanels.com (`34f85263-c082-4dcd-9440-5be7b019c49a`), explicitly confirmed by the owner.
- Project: WallPanels Estimate Platform New (`76fff733-80e1-436c-8670-4f2d3e4fbd1f`).
- Application: https://estimate-platform-production.up.railway.app
- Repository: https://github.com/Wallpanels-com/estimate-platform-new, branch `main`.
- Single Docker app serves the SPA and authenticated API, using PostgreSQL 18
  over Railway's private network and the `estimate-files` volume at `/data`.
- Seven employee accounts use unique usernames and the same `user` role.
  `email` remains the legacy API/database field name; a real email is not required.
  Temporary credentials are outside Git in a local owner-readable file.
- Self-registration and permanent deletion are disabled. Any User can manage
  employee accounts and edit the shared catalogue. Password changes revoke
  previous tokens. Passwords are stored as bcrypt hashes.

## Releases and collaboration

Railway builds pushes to `main`. Its pre-deploy command runs Alembic, then an
idempotent empty-database bootstrap. The temporary `BOOTSTRAP_*` variables must
be cleared after the first account exists. Never supply real secrets in files
committed to Git. Restarting the app does not bootstrap or overwrite users.

Every Estimate write must send `If-Match: <revision from GET /estimates/{id}>`.
The revision includes inherited Pre data for a Final branch. Stale writes return
409, missing revisions return 428. Writes serialize on the shared source row.
The SPA sends revisions automatically and polls idle views every eight seconds;
it pauses Builder refresh while editing or after an unsuccessful save. Numeric
line fields save after a short typing pause or on blur. Rejected input remains
visible. Reload before retrying a conflict; never silently overwrite it.

## Backups

`estimate-backups` is a separate private Railway Bucket in this new project.
Only reference variables connect it to the application; credentials are never
copied into source. Backups run daily while the single application replica is
running, checked hourly and after startup. An outage delays the next run until
the app returns. The PostgreSQL advisory lock prevents overlapping backup jobs.

Each archive contains:

- A native PostgreSQL 18 custom-format dump from an exported repeatable-read
  snapshot, including users, prices, estimates, audit records and document versions.
- Every file referenced by that snapshot, including photographs, voice files,
  saved PDF/XLSX versions, plus exact release assets/templates and all 13 company slides.
- A manifest with table counts, release SHA and individual SHA-256 checksums.

Image and issued-document paths are immutable and old bytes are retained. Files
are collected after the database snapshot; changed or missing files reject the
backup. The uploaded archive is downloaded again and every checksum verified
before success is recorded. No automatic backup deletion is enabled until a
retention policy is agreed; monitor bucket size as usage grows.

Authenticated operations (all employees have the same rights):

- `GET /api/v1/operations/backups`: status and completed backup metadata.
- `POST /api/v1/operations/backups`: create an additional backup.
- `POST /api/v1/operations/backups?verify=true`: also restore the database into a
  new temporary `estimate_backup_verify_<random UUID>` database, compare every
  table count and Alembic version, then remove that temporary database only.

There is deliberately no endpoint to restore over the live database. A real
disaster restore must use a new empty PostgreSQL database and a new empty file
volume, verify the manifest and restore with PostgreSQL 18 `pg_restore`, preserve
the `/data` paths, deploy the matching release, then validate before switching
the app's `DATABASE_URL`. Never use `pg_restore --clean` against the working DB.

These are daily logical/file backups, not continuous point-in-time recovery or
Railway native volume snapshots. Native volume schedules can additionally be
enabled in the corporate Railway dashboard. They are not required by the app's
backup implementation and are not claimed as configured.

## Verification

`scripts/qa_deployment.py prepare --credentials /private/path/accounts.json
--state /private/path/results.json` writes only TEST data to this exact new app.
After restarting only the new application service, run the same command with
`verify`. It checks seven logins, shared edits, conflict rejection, all three
calculator results, catalogue editing/quotes, uploads, Pre/Final Preview versus
Download byte equality, native 13-page corporate appendix, immutable versions,
XLSX, history, soft delete/restore and restart persistence. It archives its TEST
catalogue and leaves its TEST estimate recoverable in Trash. Existing estimates
are compared without being edited.

OpenAI-assisted voice/image extraction additionally needs a corporate
`OPENAI_API_KEY`; it is optional and is not fabricated during deployment.
