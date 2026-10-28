# WallPanels Estimate Platform

Corporate monorepo for the WallPanels estimating workflow. The React frontend and
FastAPI backend live in one repository and are built into one deployable image.

The application includes Estimates, Zones, Line Items, Photos, the managed Price
Book, Wall Panels/Cabinetry/Mirror calculators, Quick Estimate, Pre-Estimate and
Final Estimate PDF generation, the Project Passport XLSX export, English/Russian
UI, and Final Estimate corporate slides.

## Repository layout

```text
wallpanels-estimate-platform/
├── apps/
│   ├── frontend/                 React 18, TypeScript and Vite
│   │   ├── public/brand/         browser-safe brand assets
│   │   └── src/                  pages, components and client libraries
│   └── backend/                  FastAPI and SQLAlchemy
│       ├── app/api/v1/           HTTP routes
│       ├── app/models/           database models
│       ├── app/services/         pricing and export business logic
│       ├── app/templates/        XLSX and retained legacy templates
│       └── assets/proposals/     versioned Final Estimate slide assets
├── docs/                         architecture and feature documentation
├── scripts/                      setup, lifecycle and explicit QA utilities
├── tests/                        backend, pricing and PDF regression tests
├── Dockerfile                    single frontend/backend production image
├── docker-compose.yml            optional local PostgreSQL
├── railway.toml                  Railway build, migrations and health configuration
├── package.json                  root commands and npm workspace
└── .env.example                  environment contract without credentials
```

Runtime data is deliberately outside source control. The ignored `.local/`
directory contains local uploads, generated PDFs/XLSX, logs, QA output and process
state. The ignored `.env` contains credentials. PostgreSQL data is never stored in
Git.

## Requirements

- Node.js 22.12 or newer (`.nvmrc` pins major version 22)
- npm
- Python 3.12 (`.python-version`)
- PostgreSQL 17 recommended
- Docker only if the bundled local PostgreSQL service is desired

## First local setup

```bash
cp .env.example .env
```

Edit `.env` and replace all `change-me` values. Keep `POSTGRES_PASSWORD` and the
password inside `DATABASE_URL` identical when using Docker Compose. Then run:

```bash
npm run setup
docker compose up -d --wait db  # omit when using an existing PostgreSQL server
npm run db:migrate             # empty database; see migration notes for legacy DB
npm run dev
```

Open `http://localhost:5190`. The backend health endpoint is
`http://localhost:8010/health` and local API documentation is
`http://localhost:8010/docs`.

The lifecycle commands are:

```bash
npm run status
npm run stop
npm run dev
```

`npm run stop` stops only this app's frontend/backend processes. It does not stop
an existing shared PostgreSQL cluster and does not delete data.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection. Standard `postgresql://` provider URLs and explicit `postgresql+asyncpg://` URLs are accepted. |
| `SECRET_KEY` | Private JWT signing secret. Generate a long random value per environment. |
| `STORAGE_PATH` | Persistent uploads and generated export directory. Local default: `.local/storage`; corporate Railway volume: `/data`. |
| `ALLOWED_ORIGINS` | Comma-separated browser origins. Single-origin production does not need a wildcard. |
| `OPENAI_API_KEY` | Optional AI/voice feature key. The rest of the app works without it. |
| `MAX_UPLOAD_SIZE_MB` | Upload limit; defaults to 20. |
| `PRE_ESTIMATE_DESIGN` | `v2` by default; retained `v1` is available for controlled rollback. |
| `FRONTEND_DIST` | Optional built frontend directory served by FastAPI. Set automatically in the container. |
| `PORT` | Runtime HTTP port supplied by Railway or another platform. |
| `LOCAL_DATABASE_MODE` | Local lifecycle helper: `docker` or an externally started PostgreSQL service. |
| `LOCAL_PG_BIN`, `LOCAL_PG_DATA` | Optional local PostgreSQL executable/data paths. Never needed in a deployed container. |
| `ALLOW_REMOTE_DATABASE` | Local safety switch. Keep `false`; set `true` only for an intentional non-production development database. |
| `LOCAL_QA_EMAIL`, `LOCAL_QA_PASSWORD` | Optional ignored credentials for explicit localhost QA scripts. |
| `ALLOW_SELF_REGISTRATION` | `false`: existing employees create accounts through Team accounts. |
| `ENABLE_PERMANENT_DELETE` | `false`: retain deleted Estimates for recovery. |
| `AUTO_MIGRATE` | Keep `false`; migrations must be explicitly approved and applied with Alembic. |

Do not commit `.env`, database dumps, local storage, client images or generated
exports. `npm run verify:repo` checks the source tree for these common mistakes.

## Build and verification

```bash
npm run verify:repo
npm run typecheck
npm run build
npm test
npm run test:pdf-source
npm run test:quick
npm run test:i18n
npm run test:catalog-ui
```

`npm run qa:api` is an explicit loopback integration test. It creates disposable
QA-labelled records and export files, so use it only against an isolated local
development database. It uses `LOCAL_QA_EMAIL`/`LOCAL_QA_PASSWORD` when supplied;
otherwise it creates random credentials in ignored `.local/qa-credentials.json`.

To verify the same single-origin arrangement used by the container:

```bash
npm run build
npm run stop
.venv/bin/python scripts/dev.py serve-build
```

The frontend and `/api/v1` are then served from `http://localhost:8010`.

## Data and versioned assets

Business rules and client data have different lifecycles:

- Pricing defaults, rule engine code, PDF layouts, fonts, logo files, XLSX template,
  the shared Final title and the 13 corporate slides (appended to both Pre and
  Final presentations) are versioned in this repo.
- Users, Estimates, Zones, Line Items and managed Price Book records live in
  PostgreSQL.
- Uploaded photos and generated PDFs/XLSX live under `STORAGE_PATH`.

Back up PostgreSQL and `STORAGE_PATH` together. A database dump alone is not a
complete client-data backup because image records point to files in storage.

## Corporate Railway deployment

The owner-authorized new deployment is available at
https://estimate-platform-production.up.railway.app with mandatory employee login.
It uses a separate PostgreSQL 18 database, a persistent `/data` volume and a private
Railway backup bucket. The existing production platform is not connected or changed.
Docker builds, migrations, seven employee logins, exports, shared edits and restart
persistence have been checked on this new deployment. Backup restoration was tested
in a newly created disposable database, never over the working database.

Local customer estimates and local account databases are not automatically imported
by a Git push. Transfer approved data and matching storage as a separate migration;
never upload `.env`, `.local`, raw client backups or employee passwords to GitHub.
See [deployment verification](docs/deployment-verification.md) for the release checks.

All active employees now have one **User** role with equal shared access, personal
credentials, attributed history and immutable saved XLSX versions. PDF presentations
are generated only for Preview/Download, then their temporary files are deleted;
PDFs are never included in data backups. Corporate
SSH setup and the exact release sequence are documented in
[corporate release preparation](docs/corporate-release.md).

Additional details are in [architecture](docs/architecture.md), [QA](docs/qa.md),
[managed Price Book](docs/price-book-managed.md), [Pre-Estimate V2](docs/pre-estimate-v2.md),
and [Final Estimate corporate slides](docs/final-company-slides.md).

## Operations

The new corporate deployment and backup operations are documented in
[Railway operations](docs/railway-operations.md). Secrets and employee passwords
remain outside the repository.
