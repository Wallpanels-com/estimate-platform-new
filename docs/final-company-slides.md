# Corporate appendix for Final Estimate

## Asset

The permanent asset is `apps/backend/assets/proposals/company-slides.pdf`, copied byte-for-byte from the supplied `v3_company.pdf`. Its companion `company-slides.json` pins the SHA-256 and expected 13 pages. The PDF is 1440 × 810 pt (16:9), unencrypted, with all pages in the original order. Its existing slides contain raster artwork; the assembler preserves the original embedded streams without rasterizing or recompressing them again.

SHA-256: `a5ccab103eb00ec97bab802f5cbc07347f2b14f451695ce716ed61c7354cbb55`.

The asset directory is inside the backend package and is included by its existing Docker `COPY . .` instruction. No deployment was performed.

## Assembly and delivery

`app/services/final_estimate_service.py` calls the existing, unchanged `pdf_service.generate_pdf`, then assembles the final file using the pinned free `pypdf==6.10.0` dependency:

1. Render the unique client pages in a temporary directory.
2. Remove any exact corporate pages already present, using content/resource fingerprints rather than page count or titles. Full, partial and repeated copies are handled.
3. Fit the existing client page into the corporate 16:9 canvas with one uniform scale and centering. Landscape Letter pages gain side margins. Client text, photographs, tables and line breaks are not redesigned; their existing layout remains.
4. Clone all 13 corporate pages directly, in source order, without overlays, resizing, re-encoding or added page labels.
5. Reopen the completed file and check page count, common geometry and the 13 corporate fingerprints. Only then replace the output atomically. A failed merge cannot replace an existing complete file.

The read-only `/pdf/{id}/final-estimate` route serves this file for inline preview and for `?download=true`. Existing Final `/generate` and `/download` routes also use the assembler, so stale legacy downloads cannot bypass the appendix. Pre-Estimate and XLSX generation are unchanged.

The frontend still shares one exact PDF Blob between preview, the preview's download link and the Builder's download button for the same estimate revision. It now displays the backend's actionable error if the corporate asset is missing, corrupted, has a checksum mismatch, has a wrong page count or has inconsistent geometry. No incomplete presentation is returned.

## Local verification

- 43 backend tests pass, including the new assembly, idempotence, partial/repeated appendix, scaling/rotation, missing/corrupt asset, atomic-output and route tests.
- Frontend PDF-source tests verify identical preview/download bytes, routing, retries and readable server errors; the production build passes.
- Read-only Final generation on the existing BHUPESH estimate produced **7 client + 13 corporate = 20 pages**, 34,502,693 bytes. Independent inline/attachment API responses were byte-identical. Corporate embedded streams were byte-identical to the source. Existing customer estimates and Price Book were unchanged.
- Chrome Final Preview opened an existing isolated QA Final with **2 client + 13 corporate = 15 pages**. Both the first corporate page (3) and last page (15) were inspected. Preview and its download link reference the same Blob. Browser downloads were not clicked. The QA estimate was returned to Trash afterwards. Parallel Pre/Final mode selections were preserved; estimate contents were unchanged.
- All source corporate pages and representative client/transition/final pages were rendered and visually inspected under `.local/qa/final-company/`. The old client design was retained for the later dedicated redesign.

To inspect the result on the site: open an estimate, select **Final**, then **Preview Final Estimate**. The last 13 pages are the corporate appendix. **Download Final PDF** returns that same preview snapshot.

## Rollback

Before edits, the working renderer, PDF API, dependency list, frontend PDF loader/translations and existing tests were copied to `.local/backups/final-company-slides-20261025/` with `sha256.json`. The original `app/services/pdf_service.py` remains byte-identical to that backup.

To return to the previous wiring, stop the local app, restore those listed files from the backup to their matching project paths, rebuild the frontend and restart the app. No database rollback is required. Keep the corporate asset for reuse; it is not customer data and is not modified during generation. Do not stop the shared PostgreSQL cluster.
