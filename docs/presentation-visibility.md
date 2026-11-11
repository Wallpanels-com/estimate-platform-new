# Presentation visibility

Icon buttons beside W / VH control the saved estimate's PDFs:

- Sigma: show the project total band. Turning it off removes its background, label,
  project amount and accompanying adjustment/discount. Zone prices remain visible.
  Pre-Estimate also hides its aggregate calculation-basis and investment-range blocks.
- Calculator: generate quantity × unit-rate annotations from the saved structured
  fields in both Pre and Final (for example `140 SF × $70.00`, with `$9,800.00`
  alongside it). Turning it off hides calculation annotations. Recognizable stale
  arithmetic typed into names is removed from the displayed caption in either state;
  current saved quantities/rates supply the equation, avoiding duplicate or stale math.
  Names, descriptive scope and extended amounts remain.
  Product dimensions (`2 x 4 lumber`, `2 ft x 8 ft`) and material codes are preserved.

Dark means on; outlined means off. Both default to on for existing estimates. Buttons
have localized hover/accessible labels, keyboard focus and `aria-pressed` states. They
are disabled during unsaved edits, failed saves, saving and export preparation.

Settings apply to WallPanels and Verona, Pre and Final, and are shared by everyone
opening that estimate. The site still displays its saved base quantities and prices.
XLSX, pricing rules, company appendices, title/zone photos and image quality are unchanged.

The displayed rate includes only the adjustments already applied by the selected
renderer: Final markup/discount and cent allocation; Pre retains its existing
discount-only behavior. Rates use two decimals when possible, up to six when needed
to reconcile the displayed extended amount. Manual mismatches show the known quantity
and “Agreed amount”; fixed scope shows “Fixed amount”; unpriced items show quantity
without a made-up rate. If no short accurate rate exists, “Adjusted amount” is used.
These annotations never recalculate or overwrite stored prices.

Final names use the full text column; the calculation and amount share the next line.
All lines participate in measured wrapping/pagination. Sparse scopes retain their
caption clearance, and each continuation retains the selected zone photo.

## Persistence and rendering

`PATCH /api/v1/estimates/:id/presentation-options` accepts one or both strict boolean
fields: `show_grand_total`, `show_calculations`. Unknown fields and empty changes are
rejected. Existing authentication, page permissions, row locking, attribution, history
and `If-Match` conflict handling apply. Archived estimates cannot be changed.

The existing `pdf_layout.presentation_options` JSON stores these preferences. Updates
merge into the layout, preserving brand, cover and zone-photo choices. No migration or
bulk update of estimates is required. A newly created Final inherits the Pre selection;
existing Pre/Final branches then retain independent preferences, like their brands.

Renderers use a read-only presentation view. They never rewrite saved names or numeric
fields. Builder includes both booleans in the PDF revision key. Preview and Download
share the same loader/Blob for that saved revision. Export uses current saved server
preferences; no PDF is saved permanently by this change.

## Focused usability review

Reviewed the presentation control strip against
[Impeccable](https://github.com/pbakaus/impeccable),
[Hallmark](https://github.com/nutlope/hallmark),
[anti-ai-slop-ui](https://github.com/rwcod/anti-ai-slop-ui) and
[anti-slop](https://github.com/miqdadbadjuber/anti-slop).

The reviewed anti-ai-slop-ui source-only Python linter reported no pattern matches in
Builder or PresentationOptions. This is a heuristic, not a design-quality score.
Manual review covered hierarchy, consistent control height, EN/RU wrapping, icon labels,
keyboard focus, visible toggle state, pending/disabled behavior and PDF output. Existing
WallPanels spacing/colors/type remain; no decorative cards, gradients, emoji icons or
runtime dependencies were introduced. The repositories were consulted as references;
no third-party skills, hooks or autonomous editing workflows were installed.

## Validation

- `npm run test:catalog-ui`: real EN/RU icon toggles, independent state and disabled saves.
- `npm run test:pdf-source`: identical preview/download Blobs and cache invalidation for
  every visibility combination, brand and mode.
- `tests/test_proposal_display.py`: defaults, strict validation, read-only scope and
  pricing, markup/discount, product-dimension preservation, all 16 brand/mode/visibility
  combinations and exact corporate appendix page signatures.
- `npm run audit:workflows`: disposable local PostgreSQL schema and storage only; actual
  endpoint persistence, other-user visibility, stale-write rejection, unchanged numeric
  snapshots and SHA-256 equality of inline/download PDF bytes in all combinations.
- Local visual review: Builder EN/RU at 1512×828 and 1280×720; open Preview; rendered
  Pre/Final zone and summary pages for both brands, with controls on/off.

Only synthetic local records are used for write tests. Production verification is read-only.

## Optional presentation tax

The `%` button opens tax settings for the selected estimate branch. Tax is off by
default. Enable it, choose a percentage (initially 7%) or a fixed tax amount, then
save. Subtotal, Tax and Grand Total are calculated before saving; Subtotal and Grand
Total cannot be accidentally overwritten in this dialog. No project-size threshold
automatically enables tax.

Tax is applied to the existing presentation subtotal: Final retains its markup,
discount and project adjustment; Pre retains its discount-only basis. The displayed
subtotal is rounded to cents first, then percentage tax is rounded half-up to cents.
For example, `$38,600.00 + 7% = $41,302.00`. Tax never changes saved line-item prices,
zone amounts, the Builder's base total or XLSX.

The last Investment Summary page uses the existing reserved footer area for three
aligned columns: Subtotal, Tax and Grand Total. Labels, values and adjustment notes
are measured separately, including large amounts. The Sigma control hides this
entire block. With tax disabled, the existing presentation output is unchanged.
Both WallPanels and Verona, Pre and Final, use the same tax settings and rendering
logic. Title pages and company slides are untouched.

`GET/PATCH /api/v1/estimates/:id/presentation-tax` uses existing authentication,
permissions, revision conflict protection and edit attribution. Settings merge into
`pdf_layout.presentation_tax`; no database migration is required. New Final branches
inherit Pre tax preferences; existing branches remain independent. PDF cache revision
keys include all tax settings, and Preview/Download share the same generated bytes.

Validation includes decimal/rounding boundaries, invalid input, tax off/on, manual
amounts, saved settings across users, stale writes, unchanged XLSX cells, both brands,
both estimate modes, 1–20 zones, large amounts and text collision checks. The full
backend suite passed 182 tests (one skipped); isolated API workflows passed 537 checks.
EN/RU dialogs were visually checked at 1512×828 and 1280×720, and generated summary
pages were rendered for inspection.
