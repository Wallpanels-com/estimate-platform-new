# HR staff directory

`/hr/staff` is the shared employee directory within HR, separate from `/users` (login accounts) and candidates. Everyone granted the existing **HR department** page can view and edit Staff, employee profiles, history and reporting/collaboration connections. Both frontend route/link checks and every Staff API enforce the same HR grant; removing that grant immediately blocks subsequent API requests. Account and access management remain HR-authorized. No users' stored page grants are changed by this release. Responses remain `Cache-Control: no-store`; workbook and directory data must never be committed or bundled in frontend assets.

## Source and persistence

The initial employee workbook is uploaded through the authenticated HR-authorized `POST /api/v1/hr/staff/import` endpoint as multipart `file`. The importer reads the `Main` worksheet only, with bounded file, decompression, row and cell sizes. Other worksheets are not imported. Original cell values, row numbers, column headers, file fingerprint and document links are retained in PostgreSQL `hr_staff`. Mail links are preserved along with HTTP/HTTPS document links. Unknown extra columns remain in the employee card. Duplicate names in different source rows are kept as separate records. Re-uploading the same source rows is idempotent and never overwrites subsequent edits. Reordering an updated workbook is not a supported merge procedure; edit existing employee cards instead.

Migration `0011_hr_staff` only creates this independent table and index. It does not alter estimates, candidates, accounts or pricing. The local pre-change backup is in ignored `.local/backups/staff-20261106`. Use a database backup before reversing the migration: a downgrade drops the staff directory. Normal deployment runs migrations using the existing startup process.

## Initial hierarchy

Reporting lines do **not** exist in the source workbook. At the owner's request the initial editable structure is:

- Source employee `Kravchenko Ihor` becomes display name **Igor Kravchenko**, position **CEO**. Original values remain in source metadata.
- Administration reports to the CEO.
- Department leads report to an active administration/operations leader.
- Department staff, including project managers, report through their department lead and administration.

These starting relationships need recruiter validation. They can be changed in a person's card. This directory does not change the person's platform permissions, login, pay, or employment automatically. Status buttons prepare an edit; changes persist on **Save changes**. Version checking prevents lost updates, a transaction lock prevents concurrent reporting cycles, and changes are recorded in the existing audit log.

## Views

Table and **Team spaces** share search, department and Active/Paused/Inactive/All filters. The initial filter is Active. Structure always opens Team spaces and the entire filtered team; there is no style picker. The optional Managers scope remains available. Legacy saved layout orders remain in the database for compatibility, without exposing the retired alternatives.

The React Flow instance stays mounted when department, status, search or full screen changes. Filters update cards before paint and move the existing camera for 240 ms; reduced motion moves it instantly. Only peer reordering interpolates card positions. The department navigation, zoom, fit, minimap and full screen controls remain available. Wheel scrolling continues to scroll the page. No employee records or links are removed when filtering.

## Verification

- `python -m unittest discover -s tests -p test_staff.py -v`: Main-only parsing, source retention, hyperlinks, initial hierarchy and invalid workbook handling.
- `node scripts/test-staff-layouts.mjs`: all five coordinate layouts at 1, 3, 45 and 118 people; three filters; no overlapping cards.
- `npm run audit:workflows`: isolated local schema, HR-authorized endpoints, idempotent import, edit persistence, audit history, stale version rejection, self/cyclic manager rejection and unsafe URL validation, plus existing estimate/photo/Price Book/PDF/XLSX workflows.
- `npm run test:staff-chart`: connection validation, immutable draft/undo support, peer order, new layouts with 1/3/45/118 people and filtered non-overlap checks.
- `npm run test:staff-editor-ui`: real editor state with a synthetic canvas/transport; EN/RU connection changes, undo/redo, save payloads, 409 draft retention, cancel and deletion.
- `npm run test:staff-ui`: table/card/filter/status/save behavior, HR-member access and no-HR frontend gate with synthetic transport only.

The owner explicitly approved sharing Staff with existing HR-authorized employees. The Staff link, route guard and backend directory/chart dependencies now all use that existing HR grant; user account grants are not rewritten.

## Employee profile

Table and Team spaces open the same centered native dialog with a blurred backdrop. The profile combines a name/initials/position/status header with grouped employment, contact and personal details. Overview, Documents & notes and History tabs keep full source data and links available without displaying every field at once. Long text expands on demand. Edit profile enables fields and status controls; only Save changes persists edits. Switching tabs retains the draft, closing a dirty draft requires confirmation, and save failures preserve it. History loads only when selected. The footer and header stay visible while the body scrolls; keyboard tabs and native dialog focus/Escape behavior remain available. The profile uses the same HR authorization as the directory.
