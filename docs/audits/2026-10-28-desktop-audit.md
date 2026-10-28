# Desktop reliability and performance audit — 2026-10-28

Scope: frontend, API/database reads, autosave, photos, Price Book, document delivery, shared editing, and desktop layouts. Baseline: commit `19bc6c0`. No production data, pricing formulas, permissions, presentation assets or database migrations were changed. Mobile/tablet development was excluded at the user's request.

## Findings and changes

| Finding                                                                                                        | Resolution                                                                                                                                                                                                             |
| -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Loading 100 projects with active Final branches executed 101 SQL queries.                                      | Fetch the root register and selected Final branches in two queries; preserve existing order, authors and branch selection. The same fix covers Trash.                                                                  |
| Every displayed amount constructed another Intl formatter.                                                     | Reuse currency/date formatters; output format stays identical.                                                                                                                                                         |
| Large registers rendered every matching project on every search edit.                                          | Render 50 rows per page, defer expensive filtering, retain full-list search/filter/sort and show accurate total counts.                                                                                                |
| A new numeric draft typed while a save was pending could be dropped; a server refresh could remount the input. | Keep a stable input identity, drain the latest draft after the previous save, preserve rejected drafts, update clean fields from server refreshes. Serialize Builder writes.                                           |
| The Builder could say Saved and allow export while a debounced edit was still waiting.                         | Track pending drafts immediately, distinguish unsaved/saving/failed states, block export/mode/zone navigation until saved. Warn before closing a page with drafts.                                                     |
| Failed non-edit actions could leave the Builder permanently marked Not saved.                                  | Only retain the unsaved-edit failure state while a draft exists; preserve error notifications for unsuccessful actions.                                                                                                |
| A temporary refresh failure replaced the whole project register.                                               | Keep the last loaded register/Builder visible with a clear retry notice.                                                                                                                                               |
| Ordinary API requests could wait indefinitely.                                                                 | Add a 30-second timeout with an explicit review-before-retry message. Do not automatically retry writes or revision conflicts.                                                                                         |
| Authentication and validation errors were retried unnecessarily.                                               | Retry only transient query failures, once; preserve existing access rules.                                                                                                                                             |
| Opening an original photo in a viewer fetched it again.                                                        | Deduplicate through the existing QueryClient. Reuse original bytes in memory, GC 15 seconds after last use, revoke object URLs and clear cache on logout. No recompression, thumbnails, disk cache or quality changes. |
| XLSX generation ran synchronously in the async request handler.                                                | Run the existing generator in the thread pool; clean up temporary files on errors as well as successful delivery.                                                                                                      |
| Price Book could reject the first save of an older/default config as a conflict.                               | Compare revisions using the same effective defaults as GET /pricing/config. Genuine stale writes still return 409.                                                                                                     |
| Lazy pages could temporarily hide the navigation shell; uncaught render failures could leave a blank page.     | Add local Suspense fallbacks and a translated recovery boundary.                                                                                                                                                       |
| Save labels changed header geometry; modal openings were abrupt.                                               | Reserve status width, distinguish failures with an icon/text, add a subtle 140 ms modal entrance honoring reduced-motion preference.                                                                                   |
| Section grouping rescanned every item for each section.                                                        | Group in one pass while preserving stored English keys, row order and subtotals.                                                                                                                                       |
| Removed Price Book view tabs left unused CSS.                                                                  | Remove only those verified-unused selectors; retain existing dependencies and assets.                                                                                                                                  |

## Measurements

Same-machine local measurements, not end-to-end production timings. Five runs per comparative measurement, median reported. Fresh disposable PostgreSQL schema for each database run; generated data never entered the working schema.

| Operation                                             |             Before |            After |
| ----------------------------------------------------- | -----------------: | ---------------: |
| 100 projects, active Final branches: SQL queries      |                101 |                2 |
| Same register: DB/service median                      |           14.00 ms |          2.89 ms |
| 10,000 currency formats in Node (formatter cost only) |          153.59 ms |          2.72 ms |
| Thumbnail + full-size viewer, same photo              | 2 original fetches | 1 original fetch |
| DOM rows in the 121-project regression fixture        |                121 |       at most 50 |

After-only timings in the isolated 12-zone workflow fixture: Pre PDF 1.02 s, Final PDF 4.68 s, Pre XLSX 0.14 s, Final XLSX 0.15 s. These depend on image size, component count and hardware; they are not a production latency promise. No before/after export speedup is claimed.

## Validation

- Python suite: 121 tests, zero failures, one pre-existing optional skipped test.
- Isolated authenticated API workflow: 145 checks; two synthetic accounts, 12 zones, original photo upload/read, line items, ordering, Pre/Final branches, markup/discount, PDFs, XLSX, history, copy, Trash/restore and shared catalogue CRUD.
- True simultaneous writes from two accounts using the same revision: exactly one accepted, one rejected with 409. Stale Price Book item writes also rejected.
- Preview/download PDF page order/text parity; exports do not change saved subtotals. Existing corporate-page/layout/pricing tests retained.
- React DOM regression: delayed autosave, newer draft across refresh, rejected write/retry, clean remote refresh, photo request deduplication, 121-project pagination.
- Existing EN/RU catalogue UI, translations, PDF-source/cache tests, 27 original Quick Estimate calculation fixtures.
- Production build/typecheck, repository verification, whitespace checks.
- Desktop visual review at 1440 px: register, Builder and Quick Estimate; desktop Add Items/cabinet type form checked in the preceding baseline release. No desktop screenshot showed overlapping controls in these reviewed states.

Reproduce:

```sh
npm test
npm run test:autosave-ui
npm run test:catalog-ui
npm run test:i18n
npm run test:quick
npm run test:pdf-source
npm run audit:performance -- --label after
npm run audit:workflows
node scripts/benchmark-formatting.mjs
npm run build
npm run verify:repo
```

The two audit scripts refuse non-loopback database hosts, create a unique temporary schema, and remove only that schema in cleanup. The workflow uses temporary storage and synthetic credentials. Raw local results are under ignored `.local/audit/`.

## Limits and next work

- This is not a guarantee that every possible browser/network/input combination is covered. Final browser review of Users/Trash was interrupted by the browser tool; their backend access/recovery workflows and existing UI code were checked, but no new visual-completion claim is made for them.
- No production load testing, deployment, live staff-data mutation or new paid resources were used for the audit.
- Synchronization remains the existing 8-second polling plus revision conflicts, not realtime coediting. Edits require connectivity; rejected/unsaved drafts remain in the current page, not a durable offline queue.
- API still returns the complete lightweight register. Server-side pagination may be warranted for thousands of projects; UI pagination already bounds rendered rows.
- Large Final PDFs still take seconds. A future bounded job/concurrency layer may help many simultaneous exports without changing designs or retaining generated presentations.
- Multi-item additions remain separate transactions. A batch endpoint with an idempotency key is future work; do not blindly retry a partly completed bulk addition.
- Publication remains gated on the user's requested post-test confirmation. Rollback uses the baseline commit and does not require a database migration.
