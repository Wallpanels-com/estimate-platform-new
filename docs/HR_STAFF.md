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

Table and eight chart variants share search, department and Active/Paused/Inactive/All filters. The initial filter is Active. Charts initially show managers with reports; switch to Entire team for all matching people. Search/department filters reveal all matching staff regardless of this overview toggle. The original views remain: vertical tree, horizontal flow, radial orbits, department columns, and layered terraces.

Reference variants **07 Teams**, **08 Holi Tree**, and **09 Holi Compact** add pastel department frames/filters and a right-hand employee drawer, a classic lavender hierarchy with report counts, and a compact stacked hierarchy. Cards use real employee data and initials. Full screen, pan, zoom, fit and minimap controls remain available. Ordinary mouse-wheel scrolling continues to scroll the page. Animations respect reduced motion.

### Editing the chart

Choose **Edit chart**. Drag from the bottom outgoing circle to another card's top incoming circle, or click the two circles. **Reporting** replaces that employee's manager; self-links and reporting cycles are rejected. **Additional** creates an independent dashed collaboration connection, which does not change reporting or permissions. Select a line and use **Delete connection** or Delete/Backspace. Deleting a connection never deletes an employee. Filtered-ancestor proxy lines cannot be edited.

Drag a card by its identity/grip area to change its order among peers with the same manager. The scene smoothly returns to an automatic non-overlapping layout. Arbitrary free coordinates are intentionally not retained. **Auto arrange** clears the saved peer order for the current view. **Undo/Redo** and **Cancel** act on the local draft. Only **Save chart** persists it; changing to the table or leaving with unsaved changes warns first.

Migration `0012_hr_staff_charts` adds a separate settings table for additional edges, per-view order and chart version. `GET/PUT /api/v1/hr/staff/chart` use the same owner-only checks as Staff. Saving atomically validates chart and touched employee versions, all endpoints, duplicates and reporting cycles under the existing transaction lock before any mutation. Concurrent changes return 409 and retain the user's draft for review. Only changed manager IDs are updated on staff rows; names, source fields, contacts, employment status, estimates and prices are not modified. All changes use the existing audit log. Local checkpoint and database snapshot: ignored `.local/backups/staff-editor-20261107`.


## Verification

- `python -m unittest discover -s tests -p test_staff.py -v`: Main-only parsing, source retention, hyperlinks, initial hierarchy and invalid workbook handling.
- `node scripts/test-staff-layouts.mjs`: all five coordinate layouts at 1, 3, 45 and 118 people; three filters; no overlapping cards.
- `npm run audit:workflows`: isolated local schema, owner-only endpoints, idempotent import, edit persistence, audit history, stale version rejection, self/cyclic manager rejection and unsafe URL validation, plus existing estimate/photo/Price Book/PDF/XLSX workflows.
- `npm run test:staff-chart`: connection validation, immutable draft/undo support, peer order, new layouts with 1/3/45/118 people and filtered non-overlap checks.
- `npm run test:staff-editor-ui`: real editor state with a synthetic canvas/transport; EN/RU connection changes, undo/redo, save payloads, 409 draft retention, cancel and deletion.
- `npm run test:staff-ui`: table/card/filter/status/save behavior and private frontend gate with synthetic transport only.

To open Staff to other HR users later, change the dedicated backend owner dependency and frontend Staff gate/button together after the owner explicitly authorizes it. No employee page grants have been expanded by this feature.
