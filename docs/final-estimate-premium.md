# Final Estimate: local implementation

## Review

Open `http://localhost:5190`, open an estimate, select **Final**, then **Preview Final Estimate**. The first switch creates an independent Final branch. The existing Final is reused on subsequent switches. Both versions appear as one project in the list, showing the last selected version.

In any Final zone, open a photograph's `…` menu and choose **Set as Cover Photo** / **Выбрать для обложки**. A star marks the chosen photograph. Choosing another clears the previous selection. The choice is stored on the estimate and survives restarts. A first copy defaults to its first available photo; an estimate created directly as Final asks the user to choose. A cover without photographs uses typography, with no fabricated project image.

Preview and Download use the same assembly function and the same browser Blob for the current estimate revision. Export remains English regardless of the EN/RU UI selection. No browser download was triggered for QA.

## Presentation

- `apps/backend/app/services/final_estimate_layout.py` plans and draws the custom slides using embedded Montserrat.
- First page: the permanent shared title slide `apps/backend/assets/proposals/final-shared-title.png`, copied unchanged from the user attachment. No text, logo or footer is drawn over it.
- Second page: project title, PROJECT OVERVIEW, selected photo, transparent WallPanels / Verona logo.
- Original user backgrounds are stored without changes as `apps/backend/assets/proposals/final-background-0.png` through `final-background-3.png`. Zero is the cover; internal slides cycle 1 → 2 → 3. Their hashes and source names are in `final-backgrounds.json`.
- Zone layouts support no photos, 1–4 contained images, portrait, landscape and panoramic media. Long text is measured and split; continuations prioritize text. More than four image records can also be paginated by the renderer, while the existing Builder keeps its four-slot UI.
- Small text-only scopes receive larger typography. Panoramas get a wide composition. Four ordinary scope items fit without a lone continuation.
- The investment summary balances two columns and paginates when required; ten ordinary zones fit as 5 + 5. Amounts use the existing line totals, markup and discount values. Unpriced scope is identified and excluded from the total, never presented as a confirmed zero price.
- `final_estimate_service.py` appends the unchanged, validated 13-page `company-slides.pdf`, using pypdf without rasterizing or recompressing the appendix. Corporate pages retain their original order and page geometry. Missing or damaged corporate assets or project photos block export with an actionable error.

The approved Pre-Estimate renderers, original legacy renderer, Excel generator, pricing configuration and rule engine are unchanged.

## Linked data

`estimate_branches.py` owns cloning, mappings, override/tombstone tracking and synchronization. Three nullable fields are added idempotently: `source_estimate_id`, `branch_state`, `cover_image_id`. Existing tables, rates and calculations keep their definitions.

- Pre is the shared source; Final is a separate estimate row with independent zones, items and image files. Images are copied byte-for-byte into the destination zone directory.
- Untouched Final fields inherit when Final is opened or exported. Explicit Final edits stay protected even after reverting their displayed value.
- Final additions and removals are preserved. Source deletions remove untouched inherited data; Final-specific data is retained. Photo changes are protected by stable source-zone/slot keys, including replacement and removal.
- Derived line totals are recalculated from merged quantity and rate when one is overridden; explicit total overrides are retained. Estimate subtotals are summed from merged line items. Manual Final total overrides remain independent.
- Project-level locks serialize edits and synchronization. Creation is idempotent and the source relation has a unique index.
- Existing standalone Final estimates keep their IDs/data. First opening Pre creates a linked source copy rather than overwriting Final.
- Trash, restore and permanent project deletion operate on both versions together. No authentication or permission system was added.

## Validation and rollback

Meaningful unit checks cover complete text retention, text bounds/intersections and separators kept clear of text, 0–4 photos, cover orientations, 0/1/3/4/5/8/9/10/11/20/37 zones, override/revert behavior, derived vs manual totals, photo tombstones, corporate assembly and Preview/Download source identity. Local API QA covers bidirectional navigation, one-way inheritance, additions/deletions, moving items before deleting their former zone, independent image storage, grouped trash, direct Final creation, inverse linking and persistence after restart. Visual QA uses Chrome and rendered PDF pages at desktop size.

Private QA outputs and scripts: `.local/qa/final-premium/`. The review fixture is explicitly identified by client **QA Final Design**. Stress text is tested in memory and is not inserted into customer estimates.

The pre-change source, pricing rows and full local PostgreSQL dump are in `.local/backups/pricebook-20261025T172532/`. Its `change-files.json` records changed and added files for the existing `scripts/pricebook_backup.py --restore-source` rollback tool. Source rollback leaves the extra nullable database columns harmlessly in place. A full database rollback must use the saved dump into a separate local database first; do not overwrite current customer work or the shared PostgreSQL cluster blindly.
