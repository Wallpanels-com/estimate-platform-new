# Preview and Download share one PDF

Builder now uses one versioned PDF snapshot for the current estimate:

| Selected mode | Preview and sidebar download source |
|---|---|
| Pre-estimate | GET `/api/v1/pdf/:id/pre-estimate` — current V1/V2 renderer |
| Final | GET `/api/v1/pdf/:id/final-estimate` — preserved Final renderer |

`apps/frontend/src/lib/estimatePdf.ts` owns the source selection, filename and a
component-scoped loader. `Builder.tsx` gives that same loader to `EstimatePdfPreview`
and uses it for the Download button. Concurrent calls are deduplicated. Reopening the
preview or using either download action reuses the same Blob until the estimate ID,
saved revision or selected mode changes. Failed requests can be retried; an obsolete
request cannot clear a newer snapshot. Blob URLs are released after use.

The preview heading, iframe title, internal download label and filename now match the
selected mode. The sidebar's labels remain Preview Pre-estimate / Preview Final Estimate
and Download estimate PDF / Download Final PDF. XLSX uses its existing export path.

The new Final GET route renders into an isolated temporary directory, then deletes the
file after the response. It does not create PdfFile history or update the Estimate.
A read-only view chooses Final semantics even when requested against a saved Pre
estimate, without assigning to ORM attributes. The Final renderer itself is unchanged.
The historical POST generate / GET download routes remain available for older callers,
but Builder no longer uses that separate export pipeline.

Verification:
- `npm run test:pdf-source`: actual loader tested with fake transport and DOM; confirms
  shared Blob identity, distinct mode/revision/estimate keys, retries, race handling,
  authenticated GET URLs, filenames and download wiring. No network/file downloads.
- `npm test`: includes read-only route selection for both renderers, inline/attachment
  headers, missing estimates, failure cleanup and preserved generator/pricing contracts.
- Frontend TypeScript/Vite build and formatting pass.

After an update, reload the local Builder to clear any PDF from the previous frontend.
The user performs the actual PDF download; the agent does not click download controls.
