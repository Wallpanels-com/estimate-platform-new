# HR department

Desktop route: `/hr`. Initial production access is limited to the configured immutable owner UUID. Employees retain their existing page grants; the owner can later enable HR through Team Accounts → Access. API permissions enforce this independently of navigation.

## Workflow

1. Add a vacancy or select Marketer / Project Manager.
2. Import an `.xlsx` workbook (up to 10 MB, 5,000 non-empty rows and 100 columns). Empty worksheets/rows are ignored. Choose the worksheet and check the proposed name/email/phone mapping.
3. Check the preview and confirm. Facebook dummy leads, incomplete records and duplicate contact identities are reported separately. Confirmation is idempotent and imports into the selected vacancy only. Existing notes/statuses are never overwritten.
4. Choose 20, 50 or 100 candidates per page. The table scrolls with the document, with numbered navigation and first/last boundaries. Page size is an optional browser preference; candidate records remain in PostgreSQL.
5. Row actions: star toggles manual priority; note opens and focuses HR notes; crossed eye hides the candidate, and the open eye restores them in the Hidden view. These controls have accessible names and no visual tooltips. Hiding is reversible, stored separately from stage/notes/priority, and never deletes records.
6. Open a candidate by name. Set priority, status, HR notes, and confirmed place of residence/work. Archive candidates via status; select Archived in the status filter to restore them. Vacancies have a separate archive checkbox and Show archive control.
7. Saved changes include editor attribution and transaction-level audit history. Concurrent edits return 409 instead of overwriting another employee's changes.

Names, phone numbers and original answers are retained as supplied. No messages are sent to candidates. Candidate workbook files, credentials, import results and personal data must never be committed to Git.

## Professional sorting

HR's manual priority appears first, followed by the transparent professional match score, then newest import time. No AI is used. Only the four criteria explicitly chosen by the user are eligible; contact details, original Priority column, names, age, citizenship and location do not influence the score.

Each available questionnaire criterion has equal weight, maximum 25 points, normalized to 100. Only questionnaire questions present in that candidate's source form enter the denominator. Missing/unsupported answers score zero and remain visible for human verification; a questionnaire without recognized professional questions is unscored. This is a review aid, not an automatic employment decision.

| Criterion | Points |
| --- | --- |
| Experience | 5+ years: 25; 3–5: 20; 1–2 / 1–3: 12; below 1: 0 |
| English | C1/C2/fluent: 25; B2: 20; B1 / B1–B2: 12; initial/unspecified: 0 |
| US market | More than 3 years: 25; 1–3: 20; less than 1: 10; no: 0 |
| Technical drawings | Proficient: 25; basic: 12; none: 0 |

The candidate card shows the original question/answer and points for every criterion. Unknown wording does not receive invented qualifications. Extend the explicit rules and their tests when adding new questionnaire formats.

Phone +7 and email .ru are neutral contact flags requesting verification. They do not establish nationality/residence, change ranking, or automatically reject anyone. HR can record a location confirmed with the candidate.

## Persistence and rollback

Additive Alembic revision `0007_hr_department` introduces `hr_vacancies`, `hr_candidates`, and `hr_imports`. Data is stored in the existing PostgreSQL database, included by the existing database backup mechanism. No estimate, price, image or PDF tables/formulas are modified.

A pending import is a private database staging payload. It expires after 24 hours; expired pending payloads are cleared on subsequent uploads. A confirmed import discards its staging copy and retains the source answers in candidate records. Original Excel files are not retained on the Railway file disk.

Rollback baseline: `2420c2b`. Local backup: `.local/backups/hr/before-hr.sql.gz` (ignored by Git). Do not downgrade production after real HR imports without exporting HR records: migration downgrade drops HR tables. The application checks migration revision at startup, so image rollback requires a coordinated schema plan.

## Verification

- Parser/scoring unit tests, including contact neutrality, invalid files, test leads and field mapping.
- Disposable local PostgreSQL workflow audit: preview/confirm/deduplication, concurrent-version protection, priority ordering, audit history, archive/restore and non-owner API denial; existing Pre/Final PDF and XLSX checks remain intact.
- EN/RU access controls, catalogue UI regression, translations, production build and repository checks.
- Desktop visual checks of the candidate table and card; workbook preview/mapping exercised without modifying existing estimates.

Revision `0008_hr_candidate_visibility` adds a non-null `hidden` boolean with false default. All existing candidates retain their previous visibility. Version-checked quick-action PATCH requests update one field only; hiding/restoring does not reset the hiring stage. Local pre-migration backup: `.local/backups/hr/before-quick-actions.sql.gz`. Rollback to an earlier application revision requires a coordinated schema plan; dropping the flag would lose hidden/visible selections.

Telegram buttons appear next to phones in the register and candidate card. A known public handle entered by HR takes precedence and produces `https://t.me/username`. The optional Telegram username field accepts a handle, @handle or a public HTTPS t.me link; backend validation normalizes the stored value. Account existence and ownership are not verified by this field.

When no handle is supplied, the button uses `tg://resolve?phone=<international-number>` to ask the installed Telegram application to resolve the contact directly, avoiding the phone-only web landing page. Telegram must be installed and its privacy/account settings still apply. A separate Web fallback preserves the phone-based browser route for employees without the installed application. The backend does not discover usernames or access Telegram accounts. A native-app link cannot provide a public username when one is unknown or absent.

Formatting, an explicit `00` prefix and Facebook `p:` prefix are normalized only for the link; original phone text remains unchanged. Short local numbers, ambiguous 11-digit domestic `8…` numbers, multiple numbers, extensions and unsupported text do not produce a phone link. Nothing sends messages, looks up contacts in the background, or changes recruitment status.

Revision `0009_hr_telegram_username` adds a nullable public-handle column. Existing rows start with no handle. Version checks protect edits; older clients that omit the field preserve saved handles. Explicitly clearing the field restores the phone fallback. Local backup: `.local/backups/hr/before-telegram-handles.sql.gz`. Production rollback must coordinate the application's expected schema revision; downgrading would discard stored handles.


## AI-assisted application review (Groq)

Open a candidate → **AI review → Analyze application**. This is an on-demand aid for the recruiter, not a hiring decision or automated ranking. The existing candidate score/order/status/priority are unchanged. **Application & notes** retains all existing fields and imported answers.

The server sends only selected professional Q&A and vacancy requirements to `https://api.groq.com/openai/v1/chat/completions`. Names, contact columns, internal notes, Meta metadata and location fields are excluded; email/phone/URL fragments are redacted. Do not add sensitive personal information to professional answers or requirements. Imported text is treated as data, not model instructions. Exact source quotations in strengths/limitations are checked against submitted answers. The recruiter must verify the generated interpretation; missing experience is unknown, not proof of unsuitability.

The response includes an overview, experience summary, evidence, interview questions and a Ukrainian first-contact draft. The outreach sender is always Вікторія; it is independent of the signed-in account. Actual review author metadata still records the employee. Messages use short paragraphs and separate website/Instagram lines. Previously generated, unedited messages receive the same presentation on read without another AI request or database rewrite. Manually edited drafts are preserved. Vacancy is inserted locally. There is no automatic sending. Drafts can be edited, saved and copied. Editing a draft uses optimistic concurrency; a conflict keeps the unsaved text in the editor. Updated requirements mark the old analysis as stale. An edited saved draft survives analysis refresh.

`GROQ_API_KEY` is server-only. `HR_AI_MODEL` defaults to `openai/gpt-oss-120b`. Set these in the ignored root `.env` locally and service variables in corporate Railway. Never use a VITE-prefixed key. No new SDK/dependency is required. Provider errors, invalid evidence, timeouts and rate limits show bounded messages without leaking provider responses or credentials. Generation is limited to two simultaneous requests per worker, deduplicated per candidate across workers with a PostgreSQL transaction lock; explicit refresh has a 30-second cooldown. Unchanged reviews are reused without another provider request. No import-wide automatic analysis or background bulk transmission.

Migration `0010_hr_ai_reviews` adds a separate `hr_ai_reviews` table. Existing candidate/estimate/pricing rows are not migrated or rewritten. Reviews and message drafts persist in PostgreSQL. Rollback: revert feature code while retaining migration 0010 and the existing table, so the startup revision check remains aligned. Do not roll back to an old image expecting revision 0009 without a separate migration plan. Do not drop this table if saved drafts are needed. The local pre-migration DB copy is ignored by Git. Production deployment runs the normal Alembic upgrade.

### Creating employees with access

The owner can choose page checkboxes in **Team accounts → Add employee**. `POST /users` validates the selected page keys and creates the account and grants atomically. No selections means no accessible business pages. Existing users' grants and the owner's immutable full access are unchanged; non-owners cannot create accounts or change grants. The same checkbox component is used for later access editing.

Verification: `npm run test:hr-ai-ui`, `npm run test:access-ui`, `npm run test:hr-ui`, Python `tests/test_hr_ai.py`, and `npm run audit:workflows` in an isolated loopback schema. Provider connectivity is checked separately using synthetic application data, never by bulk-sending real candidate files.


## Review and contact workflow update

Opening a candidate's review tab now loads the saved review first and generates only when none exists or professional answers/requirements have changed. The note shortcut does not trigger AI until the review tab is opened. React Query deduplicates requests in a tab; the existing PostgreSQL lock deduplicates across tabs/users. A second requester polls the saved result instead of restarting generation. Closing a card does not discard the server result. Failed generation is not automatically retried in a loop. There is no manual refresh button; errors retain an explicit retry action.

The heading is **Application review / Разбор анкеты**, with a ScanText icon and no subtitle. Phone/email are keyboard-accessible copy buttons in both table and card; copying changes no candidate fields. Telegram/web buttons and the redundant contact-verification badge were removed. Existing stored handles, source answers and contact data remain intact. No automatic row highlighting or ranking based on telephone country codes or email domains was added.

Recruiter messages now have a formatted preview, explicit Edit message mode and safe rich clipboard output (`text/html` plus `text/plain`). Recognized greeting/section/link labels become bold; imported/model text is escaped, never interpreted as HTML. Applications that accept rich paste can preserve bold headings; clients without rich clipboard support fall back to plain text and show a corresponding notice. Messages are never sent automatically. Generated legacy messages receive section headings without another model request; manually edited drafts are preserved.

### Formatted outreach on macOS

The copy action provides plain text and HTML with explicit bold styling; it also provides native RTF when the browser advertises support. Unsupported RTF writes retry HTML before falling back to plain text. Telegram client versions may ignore HTML from a browser clipboard; the website cannot guarantee native-client paste formatting. The “Formatted text (.rtf)” action exports the current draft locally, preserving Ukrainian text, line breaks and bold section headings without Markdown markers. Open it in TextEdit and copy the rendered text for native rich-text pasting. No Telegram account connection or automatic sending is involved.
