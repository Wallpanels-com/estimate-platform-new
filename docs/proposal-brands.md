# Proposal brands — 31 October 2026

The Builder summary has a **W / VH** switch beside Grand Total and document actions, available to every employee. W (WallPanels) is the default for all existing and new estimates without an explicit choice. The selected brand is saved for that estimate/version and shared across employees.

- **W:** existing WallPanels title artwork, corner logo, and unchanged 25-page company appendix.
- **VH:** supplied Verona Pre title, supplied Verona Final template, transparent Verona logo at the lower right, and all 29 pages of `Verona Home_compressed.pdf` in original order.
- Final's **T** photo selection continues to fill the title's left frame. The zone-photo star remains independent. Pre uses the fixed supplied title.
- Generated Pre slides still start with title → Project Overview and have no slide numbering.
- Company PDFs are appended directly without rasterization, downsampling or recompression; SHA-256 and expected page counts are validated before rendering. Missing or corrupt files block the export with the existing readable error.
- Preview and Download use the same cached bytes; browser cache keys include the brand, mode and saved revision. File names include the chosen company.

## Storage and compatibility

`PATCH /api/v1/estimates/{id}/proposal-brand` accepts only `wallpanels` or `verona`. It merges `proposal_brand` into the existing `pdf_layout` JSON, preserving zone-photo selections and other settings. Existing row locks, revision conflict protection, attribution and audit history apply. No migration, price recalculation or schema change is needed.

New Final versions inherit the selected brand from their Pre source. Later brand changes are independent between existing Pre and Final versions. Duplication retains the selected brand. No existing records are rewritten by deployment.

Only approved artwork paths are selected. Each PDF canvas carries its own brand; concurrent requests do not share mutable brand state. Pricing rules, quantities, markup/discount behavior, uploaded files, roles and XLSX output are unchanged.

## Assets

WallPanels assets remain at `apps/backend/assets/proposals/`. Verona assets are at `apps/backend/assets/proposals/verona/`:

- `pre-shared-title.png` and `final-title-template.png`: exact copies of the supplied artwork.
- `company-slides.pdf`: exact supplied PDF (29 pages, 2,996,809 bytes); its checksum is pinned in `company-slides.json` and the regression test.
- `proposal-logo.png`: 2171×724 RGBA, genuine transparent background, generated non-destructively using built-in imagegen from the supplied logo.

Logo edit prompt: “Remove the white background completely and make a clean high-resolution transparent PNG, black lettering, crisp smooth edges. Preserve EXACT letter shapes, distinctive stylized E made of three horizontal bars, stylized R, triangular open A, exact tracking and proportions, HOME centered below with wide tracking. No redesign, no added elements, no shadows, no effects, no checkerboard drawn into image. Exact text VERONA and HOME. Wide aspect ratio matching original. Keep entire logo with modest transparent margins. Intended use: small corner logo in corporate proposal PDF; faithful geometry is essential.”

## Verification

- Python: 129 tests, 128 passed and one optional archival-snapshot skip.
- Isolated local PostgreSQL schema: 153 workflow checks, two employee accounts, saved choice read from fresh sessions, stale-write rejection, Final inheritance, subsequent Pre/Final independence, PDF preview/download, XLSX and audit history. Temporary schema and files removed afterward.
- Real React EN/RU toggle interaction, disabled state and PDF cache/filename tests passed. Production frontend build and repository checks passed.
- Both brands rendered in Pre and Final. Title pixels, transparent logo selection, client price/text equality across brands, exact corporate page signatures and duplicate-append prevention checked. Verona title/overview/zone pages visually inspected.
- Desktop Builder reviewed on EN/RU at actual 1440×900 and 1280×800; switch fits the summary without horizontal overflow. No mobile or tablet changes.
