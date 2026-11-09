import assert from 'node:assert/strict';
import {build} from 'esbuild';
// Exercise actual API/PDF clients in an embedded context without a browser or site writes.
const source=await build({stdin:{contents:`export {tokenStorage, notifyPortal} from './apps/frontend/src/lib/portal'; export {fetchEstimatePdf} from './apps/frontend/src/lib/estimatePdf'; export {request} from './apps/frontend/src/lib/api';`,resolveDir:process.cwd()},bundle:true,format:'esm',platform:'node',write:false,define:{'import.meta.env.VITE_API_ORIGIN':'""','import.meta.env.VITE_PORTAL_ORIGIN':'"https://edu.wallpanels.com"'}});
const messages=[];
globalThis.window={parent:{postMessage:(data,origin)=>messages.push([data,origin])}};
globalThis.location={search:'?module=hr'};
globalThis.sessionStorage={setItem(){},getItem(){return null;}};
let standaloneReads=0;
globalThis.localStorage={getItem(){standaloneReads++;return 'standalone-owner-token';},setItem(){assert.fail('Embed must not overwrite standalone tokens');}};
const mod=await import('data:text/javascript;base64,'+Buffer.from(source.outputFiles[0].text).toString('base64'));
assert.equal(mod.tokenStorage.getItem('wallpanels.token'),null);
mod.tokenStorage.setItem('wallpanels.token','scoped-embed-token');
const paths=[];
globalThis.fetch=async(path,options)=>{paths.push([path,options]);return path.includes('/pdf/')?new Response('test PDF'):new Response('{"ok":true}',{headers:{'Content-Type':'application/json'}});};
await mod.request('/auth/me');
await mod.fetchEstimatePdf({id:'one',mode:'pre',revision:'1'});
await mod.fetchEstimatePdf({id:'one',mode:'final',revision:'1'});
for(const [path,options]of paths){assert.equal(new Headers(options.headers).get('Authorization'),'Bearer scoped-embed-token',path);}
assert.equal(standaloneReads,0);
mod.notifyPortal({type:'wp:connected'});
assert.deepEqual(messages,[[{type:'wp:connected'},'https://edu.wallpanels.com']]);
mod.tokenStorage.removeItem('wallpanels.token');assert.equal(mod.tokenStorage.getItem('wallpanels.token'),null);
console.log('Embedded API and Pre/Final PDF requests use the scoped in-memory token; standalone session unchanged.');
