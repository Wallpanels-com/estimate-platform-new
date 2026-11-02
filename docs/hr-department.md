# HR department

Desktop route: `/hr`. Initial production access is limited to the configured immutable owner UUID. Employees retain their existing page grants; the owner can later enable HR through Team Accounts → Access. API permissions enforce this independently of navigation.

## Workflow

1. Add a vacancy or select Marketer / Project Manager.
2. Import an `.xlsx` workbook (up to 10 MB, 5,000 non-empty rows and 100 columns). Empty worksheets/rows are ignored. Choose the worksheet and check the proposed name/email/phone mapping.
3. Check the preview and confirm. Facebook dummy leads, incomplete records and duplicate contact identities are reported separately. Confirmation is idempotent and imports into the selected vacancy only. Existing notes/statuses are never overwritten.
4. Open a candidate by name. Set priority, status, HR notes, and confirmed place of residence/work. Archive candidates via status; select Archived in the status filter to restore them. Vacancies have a separate archive checkbox and Show archive control.
5. Saved changes include editor attribution and transaction-level audit history. Concurrent edits return 409 instead of overwriting another employee's changes.

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
