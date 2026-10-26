import assert from 'node:assert/strict';
import { build } from 'esbuild';

// Test the production loader with fake transport/DOM. No site requests or real
// browser downloads are made by this suite.
const compiled = await build({
  entryPoints: ['apps/frontend/src/lib/estimatePdf.ts'], bundle: true,
  platform: 'node', format: 'esm', write: false,
  define: { 'import.meta.env.VITE_API_ORIGIN': '""' },
});
const pdf = await import('data:text/javascript;base64,' + Buffer.from(compiled.outputFiles[0].text).toString('base64'));
const pre = { id: 'one', mode: 'pre', revision: 'r1' };
let calls = 0;
const load = pdf.createEstimatePdfLoader(async source => new Blob([`${++calls}:${source.id}:${source.mode}:${source.revision}`], { type: 'application/pdf' }));
const first = load(pre);
assert.equal(first, load(pre), 'Concurrent preview / download share one request');
const shown = await first;
assert.equal(await load(pre), shown, 'Download after preview reuses the exact Blob');
assert.equal(calls, 1);
const finalSource = { ...pre, mode: 'final' };
assert.notEqual(await load(finalSource), shown, 'Final never reuses a Pre-Estimate');
const edited = { ...finalSource, revision: 'r2' };
const editedPdf = await load(edited);
assert.notEqual(editedPdf, await load({ ...edited, id: 'two' }), 'Another estimate invalidates the snapshot');
assert.notEqual(await load({ ...edited, revision: 'r3' }), editedPdf, 'Data changes invalidate old bytes');

let attempts = 0;
const retry = pdf.createEstimatePdfLoader(async () => {
  if (++attempts === 1) throw new Error('temporary failure');
  return new Blob(['retry succeeded']);
});
await assert.rejects(retry(pre), /temporary failure/);
assert.equal(await (await retry(pre)).text(), 'retry succeeded');
assert.equal(attempts, 2);
let failOld;
const pending = new Promise((_, reject) => { failOld = reject; });
const racing = pdf.createEstimatePdfLoader(source => source.mode === 'pre' ? pending : Promise.resolve(new Blob(['final'])));
const old = racing(pre);
const fresh = await racing(finalSource);
failOld(new Error('obsolete failure'));
await assert.rejects(old, /obsolete failure/);
assert.equal(await racing(finalSource), fresh, 'An old failure must not clear the newer Final snapshot');

const paths = [];
globalThis.localStorage = { getItem: key => key === 'wallpanels.ui-language' ? 'ru' : 'local-test-token' };
globalThis.fetch = async (path, options) => {
  paths.push([path, options]);
  return new Response('fake PDF bytes', { headers: { 'Content-Type': 'application/pdf' } });
};
await pdf.fetchEstimatePdf(pre);
await pdf.fetchEstimatePdf(finalSource);
assert.deepEqual(paths.map(([path]) => path), ['/api/v1/pdf/one/pre-estimate', '/api/v1/pdf/one/final-estimate']);
assert.ok(paths.every(([, options]) => options.headers.Authorization === 'Bearer local-test-token'));
assert.ok(paths.every(([, options]) => !options.method || options.method === 'GET'));
assert.ok(paths.every(([, options]) => !options.headers['Accept-Language']), 'Russian UI must not localize PDF requests');
const missingCompany = 'The corporate slides PDF is unavailable. Restore the company slides file to generate a Final Estimate.';
globalThis.fetch = async () => new Response(JSON.stringify({ detail: missingCompany }), { status: 503, headers: { 'Content-Type': 'application/json' } });
await assert.rejects(pdf.fetchEstimatePdf(finalSource), error => error.status === 503 && error.message === missingCompany);
globalThis.fetch = async () => new Response('unavailable', { status: 500 });
await assert.rejects(pdf.fetchEstimatePdf(finalSource), /The PDF could not be generated/);
assert.equal(pdf.estimatePdfFilename('pre', 'Client/Name'), 'Pre-Estimate - Wallpanels - ClientName.pdf');
assert.equal(pdf.estimatePdfFilename('final', 'Client'), 'Final Estimate - Wallpanels - Client.pdf');

let usedBlob;
let clicked = false;
const anchor = { remove() {}, click() { clicked = true; } };
globalThis.document = { createElement: () => anchor, body: { append() {} } };
URL.createObjectURL = blob => { usedBlob = blob; return 'blob:unit-test'; };
URL.revokeObjectURL = () => {};
globalThis.setTimeout = () => 0;
pdf.downloadEstimatePdf(shown, pdf.estimatePdfFilename('pre', 'Client'));
assert.equal(usedBlob, shown, 'Download uses the same bytes supplied to the preview');
assert.equal(anchor.download, 'Pre-Estimate - Wallpanels - Client.pdf');
assert.equal(clicked, true);
console.log('PDF source tests passed: shared bytes, mode/revision isolation, retries, races, routes, filename and download wiring. No files downloaded.');
