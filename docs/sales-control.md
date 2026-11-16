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

Five independent worker loops run under one Postgres advisory lock: resource
polling, background hydration, urgent opened-client hydration, AI reviews and audio transcription. Durable cursors and jobs survive
restarts. Requests retry with backoff and surface permission/provider errors.

- All opportunities import with stable cursors beyond 10,000 records, then repeat
  a full reconciliation after five minutes. Reports explicitly flag initial partial
  imports. Removed records are marked inactive only after a complete successful scan.
- Changed opportunities use a separate read-only search about every five seconds,
  with a five-minute overlap for indexing delays. Full scans reconcile deletions.
- Phone numbers, users, recent conversations and Voice AI calls poll about every
  5–15 seconds; UI refreshes its cache every five seconds. This is eventual consistency,
  not a live audio stream or a guarantee of instantaneous CRM changes.
- Pipelines/users refresh every 15 seconds; custom fields and agents every ten minutes.
- Conversation/message history is loaded for the configured 90-day window, most
  recent first. Opening a client prioritizes missing data and refreshes cached
  messages after five seconds, contact notes/tasks after 15 seconds. Up to 500
  cached messages are shown per client. Older opportunities remain searchable.
- Notes are also read during complete opportunity scans. Internal comments are
  `TYPE_INTERNAL_COMMENT` messages; both preserve original text, author and time.
- Voice AI call logs contain transcripts; regular phone transcripts are read when
  available from GHL. For new/opened calls with no GHL transcript, existing audio
  is uploaded to Groq whisper-large-v3-turbo (25 MB maximum). Timestamps are retained,
  speakers are not inferred. Absent audio, silence and provider limits have distinct
  UI states. Old unopened calls do not trigger automatic audio transcription.
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
reanalyzed. Daily local caps default to zero (disabled), independently for analysis
and ASR. Provider quotas still apply. `SALES_AI_ARCHIVE_AUTOMATIC=false` means
only recent conversations and explicitly opened clients are automatically reviewed;
low-priority archive jobs remain dormant, without consuming requests. A rejected
HTTP 413 reduces the excerpt for retry; HTTP 429 pauses the respective worker.
Neither blocks CRM synchronization. Each accepted finding must contain an exact
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

## Conversation UI and dates

Recent conversations are sorted by their latest CRM event, not lead creation or
proof that a live call is in progress. Activity date filters select that latest
event; deal/report dates select creation time. Browser IANA timezone boundaries
are converted to UTC, including DST. Messenger history combines messages and notes
chronologically: client left, company right, yellow internal notes, blue calls,
purple opportunity events. Unknown stage details are never inferred from generic
GHL event text. Header links open GHL contact, conversation and opportunity records.
Custom selects and calendar controls support keyboard navigation.

Polling is near-real-time, not instant: provider indexing/quotas, backlog and
network delays add latency. Opportunity deletions require a full successful scan.
Messages within the imported date window, contact notes/tasks, numbers and users
are retired locally only after successful complete reconciliation. No webhook or
CRM setting is changed by the portal.
