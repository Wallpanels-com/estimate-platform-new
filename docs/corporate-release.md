# Corporate GitHub and Railway release preparation

## Scope and current state

Target repository: **Wallpanels-com/estimate-platform-new**.

HTTPS: `https://github.com/Wallpanels-com/estimate-platform-new.git`

Prepared local remote:
`git@github-wallpanels-estimate-new:Wallpanels-com/estimate-platform-new.git`

The alias deliberately requires a separate SSH configuration. It does not fall
back to a personal GitHub key. No push, cloud database migration, service creation
or deployment is authorized by this preparation document.

## Separate corporate SSH access on the Mac

Run these commands yourself in Terminal from this repository:

```bash
bash scripts/setup_corporate_ssh.sh
```

Choose a passphrase when `ssh-keygen` asks. The script refuses to overwrite any
existing file. It creates only:

- `~/.ssh/id_ed25519_wallpanels_estimate_new` — private; never copy/share/commit it.
- `~/.ssh/id_ed25519_wallpanels_estimate_new.pub` — public; upload this file only.
- `~/.ssh/config_wallpanels_estimate_new` — the corporate Host alias.

The existing `~/.ssh/config`, personal keys, global Git configuration and personal
accounts are untouched. The repository's local `core.sshCommand` uses only the
new config. Agent identities are disabled for this alias to avoid trying personal
keys.

Next:

1. Sign into the **corporate GitHub account** in the browser. Check the account
   avatar/login before continuing.
2. GitHub → Settings → SSH and GPG keys → New SSH key → Authentication key.
3. Copy the public key:

   ```bash
   pbcopy < "$HOME/.ssh/id_ed25519_wallpanels_estimate_new.pub"
   ```

4. Paste it into GitHub. Give it a clear title, e.g. `MacBook — WallPanels Estimate`.
   Authorize the key for organization SSO if the organization requires it.
5. Check the server fingerprint against GitHub's published SSH fingerprints before
   accepting the first host prompt:
   https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints
6. Test authentication using the dedicated config:

   ```bash
   ssh -F "$HOME/.ssh/config_wallpanels_estimate_new" -T git@github-wallpanels-estimate-new
   ```

   The greeting must name the intended corporate login. GitHub normally returns
   exit status 1 for a successful authentication because it provides no shell.
7. Read-only repository access check:

   ```bash
   git ls-remote origin
   git remote -v
   ```

   An empty repository can return no refs. This confirms read access, not write
   permission. The corporate account must have Write access to the target repo.

Before the first push, review the exact destination, branch and commit list. If the
remote already contains files, compare histories first; never force-push over them.
The operator must explicitly approve the first push.

## One employee role

Every active account has the role **User** and identical application permissions:
shared Estimates, Zones, photos, calculator use, Price Book editing, export,
history, saved documents and team account management. There are no Admin/Sales
gates in frontend or backend. `ck_users_uniform_role` enforces the single value in
PostgreSQL. Account disabling and password changes revoke existing sessions.

Anonymous registration is disabled by default. Existing employees create personal
accounts through Team accounts. All employee passwords are bcrypt hashes; temporary
credentials are never committed. The three requested local accounts were created
without changing existing users' passwords. Their initial credentials are in the
ignored, permission-restricted `.local/employee-access.json`.

On a new approved deployment, create the first account explicitly with
`python -m app.cli` after supplying temporary secret variables `BOOTSTRAP_EMAIL`,
`BOOTSTRAP_NAME`, `BOOTSTRAP_PASSWORD`. This command refuses a database that already
contains users and is never called automatically by app startup. Remove those
variables after creating the first User; create the remaining people in Team accounts.

Prepared by is taken from the creating account. Created by and Last edited by are
stored with the Estimate; all ORM changes have a timestamp, actor and field changes
in `audit_events`. History begins at feature activation and is not reconstructed
retroactively. Password hashes are redacted from audit payloads.

## Minimal Railway architecture

Use a **new, separately confirmed corporate project**, separate from the working
Estimate production platform:

```text
Browser → Railway application (one Docker image: React build + FastAPI)
                       ├── Railway PostgreSQL (private connection)
                       └── persistent application volume mounted at /data
```

The connected Railway inventory showed a workspace named `Wallpanels.com`, marked
`personal` by Railway. Its projects were not opened. Confirm the intended corporate
workspace/project before creating anything. The preparation has not created or
changed any Railway resources.

The app currently uses filesystem paths for ReportLab/Pillow and uploaded media.
A persistent `/data` volume is the smallest compatible first deployment. Use one
application replica with this storage arrangement. A Railway S3-compatible Bucket
is a future option requiring an upload/read/cache adapter and data migration; it is
not a drop-in `STORAGE_PATH`. No S3 credentials or SDK have been added speculatively.

Corporate title, fonts, templates and 13 company slides ship inside the image from
versioned assets. Client photos, audio and issued documents must live on `/data`.
Users, Estimates, Pre/Final branches, Price Book and history live in PostgreSQL.

Relevant Railway documentation:

- https://docs.railway.com/volumes
- https://docs.railway.com/guides/postgres-backups-restores
- https://docs.railway.com/storage-buckets

## Variables and migrations

Use `.env.railway.example` as a variable-name checklist, not as a secret file.
Create new production values for `DATABASE_URL` and `SECRET_KEY`. Mount the app
volume before the first application deployment. Use same-origin API/SPA serving.

Alembic revisions are explicit:

- `0001_baseline`: frozen, empty pre-corporate schema.
- `0002_corporate`: active accounts, token revocation, audit and document versions.
- `0003_uniform_users`: all accounts become User, with a database constraint.

For a **new empty local database**:

```bash
npm run db:migrate
```

For an existing **local** pre-Alembic database, back up first, then explicitly use
`npm run db:migrate -- --adopt-legacy`. The script validates baseline columns before
stamping. Do not stamp a production database without a separate schema review.

The application never applies schema changes at startup. The future Railway
pre-deploy command, after approval, is:

```bash
alembic -c alembic.ini upgrade head
```

`WORKDIR` in the Docker image is `/app/apps/backend`. This command is documented,
but intentionally not enabled as an automatic deployment action yet.

Do not copy local PostgreSQL data or `.local` into GitHub. If approved working data
is migrated, restore a database dump and storage together, and map all old absolute
`file_path` prefixes to `/data` in the copied target database only. This includes
images, voice, legacy PDF rows and `document_versions`. Validate every photo and
issued-document hash after migration. Do not copy local QA users into production.

## Autosave, retention and issued documents

Builder field edits save through the existing APIs. Failed saves are surfaced;
the export action is blocked while the Builder reports unsaved changes. All work
is in PostgreSQL/storage, not only browser memory. Unsaved typing before blur is
still a local form draft. Simultaneous same-field edits use the last committed
value; history records both edits. Real-time collaboration and a merge/conflict UI
remain separate future work.

Trash is reversible and no longer purged by reading the estimate list. Physical
deletion is disabled by default for everyone. Replaced/deleted image records retain
their previous bytes for recovery. Retention cleanup needs a reviewed policy.

History & saved documents in Builder can freeze a PDF or XLSX from saved data.
Each version has its input snapshot, version number, author and SHA-256. Download
and inline viewing read the same immutable file, not a fresh render. Database
triggers reject updates/deletes of issued-document metadata and audit records.
These safeguards do not replace volume backups or protect against infrastructure
owners manually replacing a disk; download verifies the stored hash.

## Backup and recovery

Use `scripts/backup_local.py` while the local application is stopped. It captures a
custom-format PostgreSQL dump, the complete storage (including issued documents),
source commit and hashes. It never connects to a remote database.

For Railway, enable scheduled backups separately for PostgreSQL and the application
volume, and retain a matching restore point. Schedule/off-site copies are not
configured by this preparation. Agree RPO/RTO and retention before production.
Recovery must be rehearsed into a separate staging database/volume, never over the
only working copy. Verify user counts, Estimate totals, all media paths and saved
document hashes before switching traffic.

## Release approval checklist

1. Finish corporate SSH setup and confirm corporate login/repository access.
2. Review repository contents and any retained historical client example fixtures.
   Do not rewrite existing Git history without explicit permission.
3. Confirm the exact first push to `Wallpanels-com/estimate-platform-new`, branch
   `main`, with no force-push.
4. Confirm a new corporate Railway project, PostgreSQL and persistent volume, their
   region/costs, variables, migrations and backup schedule.
5. Run Docker/staging verification, dependency security review and login rate-limit
   hardening before exposure. The native local application is tested; Docker is not
   installed on this Mac, so a container build is still required.

No personal GitHub, Railway, Supabase or Neon resources are used by these steps.
