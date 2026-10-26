# Local PDF media fixture

Open: http://localhost:5190/estimates/51898376-8eb6-41d2-a6d8-6cb0fb8a98fd

Title: **QA - PDF Image Variations (10 zones)**. A separate, intentionally artificial
local fixture requested by the user. BHUPESH and its images/prices are unchanged.

In Summary: **Preview Pre-Estimate → Download Pre-Estimate PDF**. Close any already
open preview and reopen it to use the corrected layout. The user performs the download;
no PDF export/download requests were made by the agent.

| Zone | References |
|---|---|
| Living Room | 1 landscape photograph |
| Staircase | 1 portrait photograph |
| Library | 1 square photograph |
| Lounge | 2 mixed photographs |
| Dining Room | 3 mixed photographs |
| Studio | 4 photographs, including a low-resolution image |
| Hallway | No image; pricing pending |
| Feature Wall | 1 unaltered copy of the supplied architectural drawing |
| Cabinetry and Wall Finishes | No image; 3 distinct, concise scope items |
| Terrace | 1 panoramic photograph |

10 zones, 31 line items, 14 uploaded images. The resulting layout contains 14 slides,
one per zone plus the cover and paginated overview/summary. The sample prices are
fictional QA inputs, never BHUPESH prices.

Photographs are downloaded once from [Lorem Picsum](https://picsum.photos/) and then
stored locally. Sizes, source URLs and SHA256 are recorded in
`tests/fixtures/pdf-media/sources.json`. All images are distinct between zones, so the
shared-reference deduplication does not conceal the gallery-count scenarios. No generated
images or external generation services are used during PDF export.

## Fix and verification

Overview/summary separators previously intersected the larger price glyphs in the next
row. Separators now follow the final text baseline of their own row with safe spacing
on both sides. The regression test measures Montserrat glyph bounds for single- and
multiple-line names and prices.

23 unit tests pass. The actual 14-slide media fixture and 8-slide BHUPESH were rendered
locally in memory, without a browser/API PDF download. Every page was checked for text
against line bounds (2 pt clearance), text against text, text against images, and content
outside the page. No violations were found. Representative image, continuation and
financial layouts were visually inspected.

Local evidence:
- `.local/qa/pdf-media/media-qa-overview.png` — complete slide contact sheet.
- `.local/qa/pdf-media/media-qa-01.png` etc. — full-size slides.
- `.local/qa/pdf-media/media-qa-layout.json` and `bhupesh-layout.json` — geometry checks.
- `.local/qa/pdf-media/fixture-report.json` — real estimate ID and zone/image counts.
- `.local/qa/pdf-media/existing-estimates-before.json` — preservation baseline.

Recreate on another local checkout: `.venv/bin/python scripts/prepare_media_qa.py`.
The script only calls localhost, downloads the public fixture images, creates its own
estimate, and refuses to duplicate an existing fixture. No schema or Price Book changes.
V1/V2 rollback remains as documented in `docs/pre-estimate-v2.md`.

## Readability refinement

After user review, removed 19 artificial repeated QA items and the 16-times repeated
paragraph. Every zone now occupies one slide; the former repeated slides 16–18 are
absent. The original client estimates remain unchanged. The QA total changes only
because its invented stress rows were removed; pricing rules are unchanged.

Names are 19 pt, details 15.5 pt, item prices 22 pt, section labels 14 pt. The investment
block is 416 pt wide beneath the scope/prices column, rather than across the slide.
The multi-image gallery now uses a 568 pt column and extends down to the footer.
Short scope details use a second column on slides without photos. Genuine long scope
still paginates without silent truncation. V1 remains frozen and selectable.

## One-slide Investment Summary

The ten-zone summary now uses two balanced columns on one slide, preserving zone
order and every price. Zone names remain 18 pt, prices 19 pt, financial totals 32 pt.
The calculation basis and preliminary range remain separate blocks below the list.
The note is shorter without changing the preliminary pricing terms. The fixture has
14 slides total. Short project summaries retain their single-column layout; unusually
large lists still paginate safely rather than shrinking the text or omitting data.
Only the V2 Pre-Estimate renderer changed; Final, XLSX and stored estimates did not.

## Caption cleanup

Removed technical image captions, shared-reference notes, the repeated client footer
and the top-right PRE-ESTIMATE label from V2. Pagination and the logo remain. The QA
client display name is now Interior Project, so its cover also has no QA IMAGE VARIATIONS
text; the QA estimate title in the project list is unchanged. Zone data, images and
all prices are unchanged. Verified text extraction and layout on all 14 slides.

## Supplied brand logo

The exact user-supplied 2244×646 PNG is stored in the frontend public brand folder
and the backend brand assets folder. The shared website Brand displays it above
Estimate Platform; dark surfaces use a CSS light variant. V2 embeds it at its native
aspect ratio in the top-left header of every slide. Verified all 14 QA slides and
all 8 BHUPESH slides: one logo per page, no text/image/rule collisions, and unchanged
estimate data. PDF checks run in memory and persist PNG evidence only. Final/V1,
pricing, XLSX and original photographs remain unchanged.

### Transparent logo revision

The opaque source is retained for reference, but is no longer used by the website
or V2. Both consume `wallpanels-verona-transparent.png`, an RGBA PNG with real alpha
(2172×724; 1,298,108 fully transparent pixels). No background blending workaround
is used. The website retains its top-left brand with Estimate Platform below;
dark surfaces turn the lettering white with a filter that preserves alpha. Every
V2 slide places the logo in the top-right header, width 210 pt, right margin 64 pt
and top margin 24 pt. All 22 reference slides pass the layout collision checks.

Asset preparation used the built-in imagegen background-extraction edit. Prompt:

> Use case: background-extraction. Edit target: supplied WALLPANELS.COM By VERONA HOME logo. Remove ONLY the entire off-white/gray paper background, including holes inside every letter, output true transparent PNG alpha. Preserve the exact black letter shapes, text, custom VERONA lettering, relative positions and original wide aspect ratio. Text verbatim: WALLPANELS.COM, By VERONA, HOME. No redesign, no changes to letterforms, no extra marks, no shadows, no white or gray rectangle, no checkerboard baked into pixels. Keep all original black typography with clean antialiased transparent edges. Trim excessive blank outer margins so this is a practical wide web/PDF logo asset; do not crop any letters.

## Short zones without photographs

Short scopes (up to three items in one section) now use a measured, centred body
composition: inset scope rows, descriptions beneath names, aligned amounts and a
full-width investment band attached below the list. Type is 21 pt for names and
17 pt for details; row height and pagination include both the list and investment.
Dense multi-section schedules retain the compact layout to avoid extra slides.
No placeholder photographs, invented scope or prices are added. The QA fixture
remains 14 slides and BHUPESH remains 8; slides 10 and 12 use the new layout.

V2 and Builder now say Price pending instead of TBD. Pending items retain their
known quantity in the presentation. Empty unit prices show Not set, with a tooltip
explaining the price per unit; the edit checkbox says Price to be confirmed.
These are presentation changes: saved values and pricing logic are unchanged.

Verified all reference slides and four in-memory edge cases (long names, long
descriptions, a dense schedule and no scope), with no overlaps or out-of-bounds
content. Regression checks cover sparse priced/unpriced scopes, text/rule clearance,
unchanged data and dense scopes keeping one slide. All 25 backend tests and the
frontend build pass. Desktop Builder checks include the pending item and edit dialog.

## One-slide Project Overview

The former overview slides 2 and 3 are combined into slide 2. Overview and Investment
Summary share measured two-column pagination when the zone list exceeds one column.
All ten zone names and prices retain their order and 18/19 pt typography; the total
remains in a separate band below the list. Oversized projects still paginate without
dropping content or shrinking type. The QA presentation now has 13 slides; BHUPESH
still has 8. Verified all slides for text, rule and image intersections, and extended
the ten-zone regression check to cover both overview and summary. All 25 tests pass.

## Shared presentation grid

Ten-zone Overview and Investment Summary now split by count, 01–05 / 06–10.
Both columns use the same measured row height and divider positions; names,
numbers and amounts share their baselines. Longer lists paginate in balanced
groups, preserving every name and price. The financial blocks below the summary
use the same 492 pt columns and 40 pt gutter.

Unpriced amounts use a hyphen in the presentation. The trailing Pricing Pending
status is omitted from displayed zone titles, without editing stored zone names.
Explicit unpriced investment totals say To be confirmed. Builder pricing controls
and all calculations remain unchanged.

All zone layouts share 64 pt outer edges. Gallery gutters now occur between cells,
with no extra offset at the outside edges; images retain their aspect ratios.
Investment bands align with the full scope column, including portrait and panorama
layouts. Sparse scopes now align with the header and footer edges as well.
Verified all 13 QA and 8 BHUPESH slides visually and for collisions. Regression
checks cover 5/5 counts, common row/divider positions, aligned financial blocks,
gallery boundaries, missing prices and unchanged input data. All 25 tests pass.
