# Pre-estimate zone ranges — shared release

Dmitry approved the rollout to all accounts on 2026-11-17. Active users with
`estimates` page access can use zone ranges. Portal sessions must have the
estimating module or no module, plus the estimates grant; an owner claim is no
longer required. `auth/me` advertises `zone_ranges_enabled`; both range routes and
the PDF renderer enforce the same access boundary.

- `GET /estimates/{id}/zone-ranges` returns the server-calculated snapshot.
- `PATCH /estimates/{id}/zones/{zone_id}/price-range` saves enabled, auto/manual,
  and optional decimal lower/upper bounds through the existing revision/row lock.
- Settings keep the existing `pdf_layout.pre_zone_ranges_trial` key so previously
  saved ranges remain available to the team; no migration or item-price
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
- PDF rendering applies the same immutable view for every authorized employee's
  Pre-estimates. Final, stored line-item prices and XLSX stay unchanged. Preview and
  download reuse the same PDF source and revision cache.

Verification: `tests/test_zone_ranges.py`, existing tax/version/photo/delivery/
branch regressions, frontend typecheck/build/i18n/PDF source tests. Browser QA uses
isolated transport fixtures; PDF QA checks measured glyph bounds and rendered
pages. No customer estimate is changed by verification.

Accounts without estimates access cannot read or edit ranges. Inactive accounts
are excluded. Existing ranges are shared; unset ranges remain disabled.
