# Presentation visibility

Two icon buttons beside W / VH control the saved estimate's PDFs:

- Sigma: show the project total band. Turning it off removes its background, label,
  project amount and accompanying adjustment/discount. Zone prices remain visible.
  Pre-Estimate also hides its aggregate calculation-basis and investment-range blocks.
- Calculator: show calculation annotations. Turning it off hides generated quantity,
  unit and rate details and recognizable inline pricing expressions such as
  `Laundry - 5 linear x 1200`. Names, descriptive scope and extended amounts remain.
  Product dimensions (`2 x 4 lumber`, `2 ft x 8 ft`) and material codes are preserved.

Dark means on; outlined means off. Both default to on for existing estimates. Buttons
have localized hover/accessible labels, keyboard focus and `aria-pressed` states. They
are disabled during unsaved edits, failed saves, saving and export preparation.

Settings apply to WallPanels and Verona, Pre and Final, and are shared by everyone
opening that estimate. The site still displays its saved base quantities and prices.
XLSX, pricing rules, company appendices, title/zone photos and image quality are unchanged.

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
