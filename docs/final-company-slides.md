# Corporate appendix for Pre-Estimate and Final Estimate

## Asset

The permanent asset is `apps/backend/assets/proposals/company-slides.pdf`, copied byte-for-byte from the user-approved `v3_company (2)_compressed.pdf` on October 28. Its companion `company-slides.json` pins the SHA-256, expected 13 pages and content/resource signatures. The PDF is 1440 × 810 pt (16:9), unencrypted, with its original crop-box origin and page order preserved. It weighs 1,949,021 bytes. Its embedded corporate images are not recompressed or rasterized again.

SHA-256: `1548803e25f92b922f0c67fb6e44fa336cf2808e182c4391010cf13eea3b0e3b`.

The asset directory is inside the backend package and included by Docker. Generation has no dependency on the original Downloads folder.

## Assembly and delivery

`final_estimate_layout.generate_final_client` and the selected Pre renderer generate client pages. Both then use the shared assembler in `final_estimate_service.py` and pinned free `pypdf==6.10.0`:

1. Render the unique client pages in a temporary directory.
2. Remove any exact corporate pages already present, using content/resource fingerprints rather than page count or titles. Full, partial and repeated copies are handled.
3. Fit the existing client page into the corporate 16:9 canvas with one uniform scale and centering. Landscape Letter pages gain side margins. Client text, photographs, tables and line breaks are not redesigned; their existing layout remains.
4. Clone all 13 corporate pages directly, in source order, without overlays, resizing, re-encoding or added page labels.
5. Reopen the completed file and check page count, common geometry and the 13 corporate fingerprints. Only then replace the output atomically. A failed merge cannot replace an existing complete file.

Both `/pdf/{id}/final-estimate` and `/pdf/{id}/pre-estimate` serve the complete presentation for inline preview and `?download=true`. Compatibility `/generate` and `/download` routes also use the assembler. XLSX generation is unchanged. Final-only markup is hidden from Pre through a read-only view; saved line/zone prices and workspace totals remain base amounts. Existing discount behavior in PDF/XLSX remains intact.

Client JPEGs are embedded without re-encoding; other raster samples may use reversible PNG predictors. No images are downsampled. Fonts and text remain in their existing format. A 12-zone/12-photo local Final fixture fell from 56.17 MB to 7.23 MB; a Pre fixture with the appendix is 2.14 MB. These are examples, not a hard cap: large original uploads can still produce larger files. Generated PDFs remain temporary/download-only.

The frontend still shares one exact PDF Blob between preview, the preview's download link and the Builder's download button for the same estimate revision. It now displays the backend's actionable error if the corporate asset is missing, corrupted, has a checksum mismatch, has a wrong page count or has inconsistent geometry. No incomplete presentation is returned.

## Initial implementation verification (October 25, original corporate asset)

- 43 backend tests pass, including the new assembly, idempotence, partial/repeated appendix, scaling/rotation, missing/corrupt asset, atomic-output and route tests.
- Frontend PDF-source tests verify identical preview/download bytes, routing, retries and readable server errors; the production build passes.
- Read-only Final generation on the existing BHUPESH estimate produced **7 client + 13 corporate = 20 pages**, 34,502,693 bytes. Independent inline/attachment API responses were byte-identical. Corporate embedded streams were byte-identical to the source. Existing customer estimates and Price Book were unchanged.
- Chrome Final Preview opened an existing isolated QA Final with **2 client + 13 corporate = 15 pages**. Both the first corporate page (3) and last page (15) were inspected. Preview and its download link reference the same Blob. Browser downloads were not clicked. The QA estimate was returned to Trash afterwards. Parallel Pre/Final mode selections were preserved; estimate contents were unchanged.
- All source corporate pages and representative client/transition/final pages were rendered and visually inspected under `.local/qa/final-company/`. The old client design was retained for the later dedicated redesign.

To inspect the result on the site: open an estimate, select **Final**, then **Preview Final Estimate**. The last 13 pages are the corporate appendix. **Download Final PDF** returns that same preview snapshot.

## Rollback

Before edits, the working renderer, PDF API, dependency list, frontend PDF loader/translations and existing tests were copied to `.local/backups/final-company-slides-20261025/` with `sha256.json`. The original `app/services/pdf_service.py` remains byte-identical to that backup.

To return to the previous wiring, stop the local app, restore those listed files from the backup to their matching project paths, rebuild the frontend and restart the app. No database rollback is required. Keep the corporate asset for reuse; it is not customer data and is not modified during generation. Do not stop the shared PostgreSQL cluster.
