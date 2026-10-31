# Proposal branding — 31 October 2026

- The active Pre-estimate V2 starts with `pre-shared-title.png`, unchanged. The existing project-information page follows it.
- Final starts with `final-title-template.png`. The **T** button on any Final zone photo selects the left-hand title photo, using the existing saved `cover_image_id` field. If no selection is available, the first estimate photo is used. The cover frame uses a centered crop; zone photos keep their uncropped fitting.
- The star independently selects the zone's presentation photo. The limit stays four photos per zone.
- Generated internal slides use `proposal-background.png`, embedded Arial/Arial Bold, a neutral black/gray palette, and transparent `proposal-logo.png` at the lower right. Photo/total geometry reserves the logo footer strip.
- Title slides have no additional corner logo. Corporate pages retain their supplied design and existing logos.
- Both Pre and Final append all **25** pages from `company-slides.pdf`, copied byte-for-byte from the approved `Wallpanels_compressed.pdf`. The manifest pins the SHA-256 digest, page count and page signatures. No recompression or image conversion is applied to the corporate PDF.
- The frozen V1 renderer remains an archival reference. Production uses V2.
- Browser PDF cache keys were incremented so the new release does not reuse an older presentation snapshot.

No database schema, saved prices, calculations, permissions or XLSX generator changed.
