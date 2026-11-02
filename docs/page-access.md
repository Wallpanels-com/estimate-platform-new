# Owner-managed page access — 2 November 2026

Dmitry opens **Team accounts → Access**, checks the required pages and saves. Current page keys are `estimates`, `quick_estimate`, `price_book`, `users`, and `trash`. No HR page is introduced in this release. Staff retain the single User role; page grants are separate from roles.

## Storage and rollout

Migration `0006_user_page_access` adds one nullable JSON column, `users.page_access`. NULL preserves access to all five existing pages; an explicit empty list grants no work pages. Existing employees are not bulk-restricted or rewritten. Newly created accounts start with an empty grant list until the owner chooses their pages. The access editor starts with their effective grants. Changes and editor attribution are captured by the existing user audit hook. Concurrent editors use the user's `updated_at` and a row lock; stale saves return 409 and preserve the unsaved choices.

`ACCESS_MANAGER_USER_ID` identifies the active owner by immutable UUID, never by a mutable name, login or role. During transition the existing owner-only `AGENTATION_USER_ID` is a fallback, but deployment should set the dedicated variable so removing the feedback toolbar cannot remove account management. The corporate Dmitry account was verified through its authenticated profile before configuring this value. Owner identity and privileges cannot be assigned through any user-editing API. The owner always retains all five grants and cannot disable their own account.

Only this owner can create/edit employee accounts, reset another employee's password or assign page grants. Employees granted the Team accounts page see the list read-only. This prevents changing an owner's password, or creating an unrestricted account, to bypass page restrictions. Self-service profile/password changes remain available to authenticated employees. Optional public self-registration creates an account with no work-page grants.

## Backend enforcement

All authenticated APIs pass through the same authorization boundary. Protected pages cannot be bypassed by a direct URL, older token, photo URL or PDF/XLSX download link. Access grants are read with the user on every request, so backend revocation is immediate. Unknown future protected APIs fail closed until explicitly mapped.

- Estimates grants access to the shared saved-estimate register and its projects, including previously saved Quick projects.
- Quick Estimate permits that creation/calculation page and working with saved Quick projects, but cannot expose a regular Pre/Final estimate or convert a Quick project to Pre/Final.
- Price Book permits editing rates/categories/items. Employees without this grant can still read the rates and quote existing items inside an allowed estimate/calculator; they cannot change the shared book. Related create controls in Add Items are hidden.
- Trash permits its listing, restore and existing delete rules. Granting Trash does not grant edits to active projects.
- Global audit and backup operations are owner-only. Per-estimate history follows that estimate's access.

Foreign zone IDs are rejected when creating/moving line items, preventing a Quick-only employee from writing into a different estimate's zone. Normal calculations and valid item moves are unchanged.

## Frontend

A shared page registry drives menu filtering, page guards, checkbox labels and the first permitted landing page. With zero grants, the user sees an access-request screen and can sign out; no redirect loop occurs. The profile refreshes every 15 seconds and on window focus; a backend 403 also requests a refresh. Dirty modal state is retained on save/network/conflict errors. The editor cannot be closed during a save.

EN/RU labels and the existing desktop design are retained. Mobile/tablet changes are excluded. The dialog was visually checked on desktop at 1280×800, and the real React tests check both languages, owner-only controls, hidden navigation, direct-route rejection and conflict handling.

## Checks and rollback

- Local database backup before migration: `.local/backups/before-page-access-20261102.sql.gz` (ignored by Git). Code baseline: `6dc42f9`.
- The migration was applied to loopback PostgreSQL before restarting the local app.
- Isolated workflow audit: 188 checks in a disposable schema with two synthetic users; grants persist across sessions, old tokens immediately obey changed grants, owner lockout and privilege escalation are denied, Pre/Final PDFs and XLSX still work. No real employee grants or estimates were changed during tests.
- Unit tests cover the page policy, uppercase UUID paths, HTTP-method spoofing against Price Book, owner identity, empty grants, stale changes and foreign-zone writes.
- `npm run test:access-ui`, catalogue UI tests, i18n, PDF source tests, production build and repository verification pass.

Railway uses its existing reviewed `app.deploy` pre-deploy migration step. This migration changes no prices, estimates, files or document generators. A rollback to code expecting revision 0005 requires a coordinated migration downgrade; do not blindly roll back the image because startup checks the expected revision. Downgrade removes the grants column and therefore loses configured restrictions; export grants first and only perform it with explicit approval.
