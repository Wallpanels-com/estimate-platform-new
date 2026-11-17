# Pre-estimate zone ranges — owner trial

Only the immutable configured owner (`ACCESS_MANAGER_USER_ID`, with the existing
`AGENTATION_USER_ID` fallback) can use this trial. Portal sessions must also have
an owner claim and the estimating module or no module. `auth/me` advertises
`zone_ranges_enabled`; both range routes enforce the same boundary. Role labels
and page grants cannot enable it for other employees.

- `GET /estimates/{id}/zone-ranges` returns the server-calculated snapshot.
- `PATCH /estimates/{id}/zones/{zone_id}/price-range` saves enabled, auto/manual,
  and optional decimal lower/upper bounds through the existing revision/row lock.
- Settings live in `pdf_layout.pre_zone_ranges_trial`; no migration or item-price
  edits. Generic layout updates preserve this reserved key. Estimate duplication
  remaps zone IDs; a new Final does not inherit the settings.
- Auto = the zone's discounted base × 0.90 / 1.15, rounded to cents. Final-only
  markup is excluded, as in the existing Pre renderer.
- Manual bounds are prices **after discount, before tax**. They remain fixed if
  items or discount change. A changed calculation basis raises a review hint.
- With at least one enabled zone, sum the zone lower and upper bounds separately;
  exact zones and unassigned scope contribute the same price to each bound.
  Percent tax applies to each aggregate bound; fixed tax is added once to each.
- With all ranges disabled, the old project-wide range remains in force.
- PDF rendering applies an immutable view only for the owner's Pre-estimates.
  Other users, Final, stored line-item prices and XLSX stay unchanged. Preview and
  download reuse the same PDF source and revision cache.

Verification: `tests/test_zone_ranges.py`, existing tax/version/photo/delivery/
branch regressions, frontend typecheck/build/i18n/PDF source tests. Browser QA uses
isolated transport fixtures; PDF QA checks measured glyph bounds and rendered
pages. No customer estimate is changed by verification.

Do not expand availability to employees until Dmitry approves the trial.
