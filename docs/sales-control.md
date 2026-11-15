# Sales Control

`/sales-control` is a private owner pilot in the existing Estimator. The frontend
uses `/auth/me.sales_control_enabled`; all `/api/v1/sales/*` requests independently
require the configured active owner's immutable UUID. Employee page grants and
admin roles cannot grant access. Embedded sessions additionally require the portal
owner claim and the estimating module. No user accounts or grants are modified.

## Data and boundaries

The existing PostgreSQL database stores four new `sales_*` tables: CRM snapshots,
resumable synchronization state, jobs, and AI reviews. Migration 0016 is additive.
Supabase is not required. Keys are server environment variables, never Vite variables
or frontend payloads. Responses are authenticated and `Cache-Control: no-store`.

The GHL client has an allowlist of GET read endpoints and exactly one fixed POST:
`/opportunities/search` with the `opportunities.readonly` scope. This is GHL's
[documented read-only advanced search](https://marketplace.gohighlevel.com/docs/ghl/opportunities/search-opportunities-advanced/),
not a create/update operation. Its body is constructed internally from sync dates
and pagination cursors. No CRM mutation, message sending, mark-as-read, number
assignment, AI-agent update, account update, or deletion is implemented. Groq receives
conversation text for analysis, as authorized, but has no tools or CRM credentials.

## Synchronization

Three independent worker loops run under one Postgres advisory lock: resource
polling, contact/message hydration, and AI reviews. Durable cursors and jobs survive
restarts. Requests retry with backoff and surface permission/provider errors.

- All opportunities import with stable cursors beyond 10,000 records, then repeat
  a full reconciliation after five minutes. Reports explicitly flag initial partial
  imports. Removed records are marked inactive only after a complete successful scan.
- Changed opportunities use a separate read-only search about every 60 seconds,
  with a five-minute overlap for indexing delays. Full scans reconcile deletions.
- Phone numbers, users, recent conversations and Voice AI calls poll about every
  60 seconds; UI refreshes its cache every 10–30 seconds. This is eventual consistency,
  not a live audio stream or a guarantee of instantaneous CRM changes.
- Pipelines, custom fields and agent directory refresh every ten minutes.
- Conversation/message history is loaded for the configured 90-day window, most
  recent first. Opening a client prioritizes missing data and refreshes cached
  messages after 60 seconds, contact notes/tasks after five minutes. Up to 500
  cached messages are shown per client. Older opportunities remain searchable.
- Notes are also read during complete opportunity scans. Internal comments are
  `TYPE_INTERNAL_COMMENT` messages; both preserve original text, author and time.
- Voice AI call logs contain transcripts; regular phone transcripts are read when
  available from GHL. Missing transcripts are explicitly marked, never invented.
  Audio is served through an authenticated backend proxy on demand.

## Features and interpretation

Activity cards, searchable/filterable opportunities, client history, calls and
transcripts, evidence-linked Groq reviews, lost/abandoned lead review, current
pipeline/stage/owner reports, CSV/XLSX exports, and phone routing inventory.
A live attention banner links to reviews with concerns. There are no external
email, Slack or desktop notifications. A missing direct phone owner is not enough
to call a number free: ring groups, forwarding and Voice AI routing are displayed.

Lead review initially means CRM statuses `lost` / `abandoned`. The latest employee
note is shown verbatim; it is not automatically treated as the loss reason or proof
of lead quality. The final business definition can be supplied later.

Reports are current snapshots. Date filters refer to opportunity creation time.
There is no invented historical conversion or manager ranking. Detected stage,
status and assignment changes are stored from integration activation onward.

Groq runs after available calls and after two minutes of message inactivity.
Input is bounded to 60 messages / 45,000 characters; unchanged sources are not
reanalyzed. The daily request budget (excluding rejected HTTP 429 requests) defaults to 150
UTC; queued work resumes the next day. Each accepted finding must contain an exact
quote from an included source. Strengths, issues and optional improvements are
separate. Empty findings are valid. Reviews remain AI suggestions, not verified
employee violations. No approved Sales Ops policy was supplied, so the prompt
forbids inventing pricing, territory, delivery or company-policy rules.
Provider rate limits pause the whole AI queue according to `Retry-After`, without
blocking CRM synchronization or spending the daily budget on rejected retries.

## Operation

Configure `SALES_GHL_LOCATION_ID`, `SALES_GHL_TOKEN`, `SALES_GROQ_API_KEY` and
`SALES_SYNC_ENABLED=true` in the app service. Owner identity reuses the existing
`ACCESS_MANAGER_USER_ID` / `AGENTATION_USER_ID`; do not change employee grants.
The connection-status panel displays each resource's last successful read, queue,
errors and daily AI limit. Set `SALES_SYNC_ENABLED=false` and restart to pause the
mirror without changing CRM data. Existing cached data stays owner-only.

Validation: unit tests cover immutable owner identity, portal module boundary,
GET-only portal endpoints, fixed upstream read/search operations, exact quote
validation, cursor overlap, incomplete-list protection, credential scrubbing and
timezones. Local/production QA additionally checks real GHL/Groq results, exports,
responsive UI and employee denial.
