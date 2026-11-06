# Private HR staff directory

`/hr/staff` is a directory of employees, separate from `/users` (login accounts) and HR candidates. It currently uses the **existing configured platform owner ID** (`ACCESS_MANAGER_USER_ID`, falling back to `AGENTATION_USER_ID`). HR page access alone does not grant access. Every Staff API checks the owner, including import, updates and history. Responses are `Cache-Control: no-store`; the workbook and directory data must never be committed or bundled in frontend assets.

## Source and persistence

The initial employee workbook is uploaded through the authenticated owner-only `POST /api/v1/hr/staff/import` endpoint as multipart `file`. The importer reads the `Main` worksheet only, with bounded file, decompression, row and cell sizes. Other worksheets are not imported. Original cell values, row numbers, column headers, file fingerprint and document links are retained in PostgreSQL `hr_staff`. Mail links are preserved along with HTTP/HTTPS document links. Unknown extra columns remain in the employee card. Duplicate names in different source rows are kept as separate records. Re-uploading the same source rows is idempotent and never overwrites subsequent edits. Reordering an updated workbook is not a supported merge procedure; edit existing employee cards instead.

Migration `0011_hr_staff` only creates this independent table and index. It does not alter estimates, candidates, accounts or pricing. The local pre-change backup is in ignored `.local/backups/staff-20261106`. Use a database backup before reversing the migration: a downgrade drops the staff directory. Normal deployment runs migrations using the existing startup process.

## Initial hierarchy

Reporting lines do **not** exist in the source workbook. At the owner's request the initial editable structure is:

- Source employee `Kravchenko Ihor` becomes display name **Igor Kravchenko**, position **CEO**. Original values remain in source metadata.
- Administration reports to the CEO.
- Department leads report to an active administration/operations leader.
- Department staff, including project managers, report through their department lead and administration.

These starting relationships need recruiter validation. They can be changed in a person's card. This directory does not change the person's platform permissions, login, pay, or employment automatically. Status buttons prepare an edit; changes persist on **Save changes**. Version checking prevents lost updates, a transaction lock prevents concurrent reporting cycles, and changes are recorded in the existing audit log.

## Views

Table and five fixed-connection chart variants share search, department and Active/Paused/Inactive/All filters. The initial filter is Active. Charts initially show managers with reports; switch to Entire team for all matching people. Search/department filters reveal all matching staff regardless of this overview toggle. Views: vertical tree, horizontal flow, radial orbits, department columns, and layered terraces. Chart cards are not draggable or connectable; background pan, zoom, fit and minimap controls remain available. Chart nodes open the same employee card as the table. The chart starts at readable zoom near its root; use Fit view for a full overview, and department filtering for a closer view. When a manager is filtered out, a dotted connection leads to the nearest visible ancestor and does not change stored reporting lines. Animations respect reduced motion.

## Verification

- `python -m unittest discover -s tests -p test_staff.py -v`: Main-only parsing, source retention, hyperlinks, initial hierarchy and invalid workbook handling.
- `node scripts/test-staff-layouts.mjs`: all five coordinate layouts at 1, 3, 45 and 118 people; three filters; no overlapping cards.
- `npm run audit:workflows`: isolated local schema, owner-only endpoints, idempotent import, edit persistence, audit history, stale version rejection, self/cyclic manager rejection and unsafe URL validation, plus existing estimate/photo/Price Book/PDF/XLSX workflows.
- `npm run test:staff-ui`: table/card/filter/status/save behavior and private frontend gate with synthetic transport only.

To open Staff to other HR users later, change the dedicated backend owner dependency and frontend Staff gate/button together after the owner explicitly authorizes it. No employee page grants have been expanded by this feature.
