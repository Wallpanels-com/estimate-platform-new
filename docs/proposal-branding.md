# Proposal branding — 31 October 2026

- The active Pre-estimate V2 starts with `pre-shared-title.png`, unchanged. Project Overview follows immediately, without a second client title or Prepared by page. Generated Pre slides have no page numbers. Shared architectural drawings remain on a Project Reference page after the overview.
- Final starts with `final-title-template.png`. The **T** button on any Final zone photo selects the left-hand title photo, using the existing saved `cover_image_id` field. If no selection is available, the first estimate photo is used. The cover frame uses a centered crop; zone photos keep their uncropped fitting.
- The star independently selects the zone's presentation photo. The limit stays four photos per zone.
- Generated internal slides use `proposal-background.png`, embedded Arial/Arial Bold, a neutral black/gray palette, and transparent `proposal-logo.png` at the lower right. Photo/total geometry reserves the logo footer strip.
- Title slides have no additional corner logo. Corporate pages retain their supplied design and existing logos.
- With WallPanels selected (the default), both Pre and Final append all **25** pages from `company-slides.pdf`, copied byte-for-byte from the approved `Wallpanels_compressed.pdf`. The manifest pins the SHA-256 digest, page count and page signatures. No recompression or image conversion is applied to the corporate PDF.
- The frozen V1 renderer remains an archival reference. Production uses V2.
- Browser PDF cache keys were incremented so the new release does not reuse an older presentation snapshot.

No database schema, saved prices, calculations, permissions or XLSX generator changed.

Generation reuses static artwork within each document and limits lossless packing to client pages. Corporate streams are appended unchanged; photo pixels and resolution are preserved.

## Generation measurement (local, 31 October 2026)

Same three-zone fixture (4/1/3 components, three unchanged uploaded images), approved 25-page appendix, three sequential calls per mode in a fresh Python process. Times include complete assembly and verification, exclude extraction/rendering:

| Mode | Before, seconds | After, seconds |
| --- | --- | --- |
| Pre | 4.961 / 4.856 / 4.869 | 4.280 / 1.541 / 1.548 |
| Final | 5.273 / 5.342 / 5.336 | 3.193 / 1.894 / 1.888 |

The first call includes artwork packing cache misses; the application already warms approved static artwork at startup. These are local measurements, not a promise of identical Railway latency. No image resampling, lossy compression, or saved estimate edits were introduced.

The optional Verona Home profile (VH switch, separate titles/logo and 29-page appendix) is documented in [proposal brands](proposal-brands.md).
