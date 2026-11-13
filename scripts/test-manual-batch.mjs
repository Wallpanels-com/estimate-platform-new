/** Exercise the real React item editor and picker in an isolated DOM; no browser or database writes. */
import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm, readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { build } from "esbuild";
import { JSDOM } from "jsdom";


const dom = new JSDOM(
  '<!doctype html><html><body><div id="root"></div></body></html>',
  { url: "http://localhost:5190" },
);
for (const name of [
  "window",
  "document",
  "HTMLElement",
  "HTMLInputElement",
  "HTMLDialogElement",
  "Event",
  "MouseEvent",
  "KeyboardEvent",
  "Node",
  "FormData",
  "localStorage",
])
  globalThis[name] = dom.window[name];
Object.defineProperty(globalThis, "navigator", {
  value: dom.window.navigator,
  configurable: true,
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
// Workflow assertions use reduced motion; enter/exit timing has its own regression test.
window.matchMedia = () => ({ matches: true });
const nativeMatches = HTMLElement.prototype.matches;
HTMLElement.prototype.matches = function (selector) {
  return selector === ":popover-open"
    ? this.dataset.open === "true"
    : nativeMatches.call(this, selector);
};
HTMLElement.prototype.showPopover = function () {
  this.dataset.open = "true";
  this.dispatchEvent(new Event("toggle"));
};
HTMLElement.prototype.hidePopover = function () {
  delete this.dataset.open;
  this.dispatchEvent(new Event("toggle"));
};
HTMLDialogElement.prototype.showModal = function () {
  this.open = true;
};
HTMLDialogElement.prototype.close = function () {
  this.open = false;
};

const dir = await mkdtemp(resolve('.local/batch-ui-'));
try {
 const compiled=await build({stdin:{contents:`export * from './apps/frontend/src/lib/manualBatch'; export {default as ManualBatch} from './apps/frontend/src/components/ManualBatch'; export {LanguageProvider} from './apps/frontend/src/lib/i18n'; export {ApiError} from './apps/frontend/src/lib/api'; export {createElement,act} from 'react'; export {createRoot} from 'react-dom/client';`,resolveDir:process.cwd(),loader:'tsx'},bundle:true,platform:'node',packages:'external',format:'esm',jsx:'automatic',write:false,define:{'import.meta.env.VITE_API_ORIGIN':'""'}});
 await writeFile(resolve(dir,'app.mjs'),compiled.outputFiles[0].contents);
 const {decimal,parseList,rowError,calculation,blankRow,ManualBatch,LanguageProvider,ApiError,createElement:h,act,createRoot}=await import(pathToFileURL(resolve(dir,'app.mjs')));
 for (const [raw,expected] of [['17,6','17.60'],['$1,558.61','1558.61'],['1.558,61','1558.61'],['1 558,61','1558.61'],['0','0.00'],['-10',null],['1e3',null],['3000?',null],['1,2,3',null]]) assert.equal(decimal(raw),expected,raw);
 const parsed=parseList(`Kitchen cabinets lower and upper - 17,6 Lin x 1200 = 21120
Upper cabinets glass doors - 1500
Tall cabinetry - 7 Lin x 1100 = 7700
Bar:
Lower cabinetry - 4 x 550 = 2200
2 shelves with led - 600
Bar pocket doors - 3000?
Panels for fridge doors - 40 sq ft x 80 = 3200
Island base - 9 Lin x 550 = 4950
Table base - 5 Lin x 500 = 2500`);
 assert.equal(parsed.length,9); assert.equal(parsed[0].name,'Kitchen cabinets lower and upper');assert.equal(parsed[0].quantity,'17.60');assert.equal(parsed[0].unit,'LF');assert.equal(parsed[0].total_price,'21120.00');
 assert.equal(parsed[3].section,'Bar');assert.equal(parsed[5].review,true);assert.equal(parsed[6].unit,'SF');assert.equal(rowError(parsed[0]),null);assert.ok(rowError(parsed[5]));
 assert.equal(parseList('LED Strip Light – Dimmable — $519.33')[0].name,'LED Strip Light – Dimmable');
 assert.equal(parseList('Panel 24-A\t620')[0].total_price,'620.00');
 const longName='A'.repeat(501);assert.equal(parseList(longName+' - 10')[0].name,longName);assert.ok(rowError(parseList(longName+' - 10')[0]));
 const mismatch=parseList('Test - 3 x 10 = 20')[0];assert.ok(rowError(mismatch));mismatch.accept_total=true;assert.equal(rowError(mismatch),null);
 assert.equal(calculation({...blankRow(),quantity:'0.05',unit_price:'0.10'}),'0.01');
 assert.ok(rowError(parseList('Unknown amount - ask Katya')[0]));
 assert.throws(()=>parseList(Array(201).fill('Item - 5').join('\n')));
 for (const language of ['en','ru']) {
  localStorage.setItem('wallpanels.ui-language',language);
  const root=createRoot(document.getElementById('root'));let requests=[],closed=0;
  await act(async()=>root.render(h(LanguageProvider,null,h(ManualBatch,{onBusy:()=>{},onClose:()=>closed++,onAdd:async data=>{requests.push(data); if(requests.length===1) throw new TypeError('Network failed');}}))));
  const button=text=>[...document.querySelectorAll('button')].find(b=>b.textContent===text);
  const input=async(el,value)=>act(async()=>{const proto=el.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;Object.getOwnPropertyDescriptor(proto,'value').set.call(el,value);el.dispatchEvent(new Event('input',{bubbles:true}));});
  await act(async()=>button(language==='en'?'Paste list':'Вставить список').click());
  await input(document.querySelector('textarea'),'Panels - 140 SF x 70 = 9800\nDoors - 1500');
  await act(async()=>button(language==='en'?'Review list':'Разобрать список').click());
  assert.equal(document.querySelectorAll('.batch-entry').length,2);
  assert.match(document.querySelector('.batch-toolbar strong').textContent,/11,300/);
  await act(async()=>document.querySelectorAll('.batch-actions')[0].querySelectorAll('button')[2].click());
  assert.equal(document.querySelector('.batch-entry input').value,'Doors');
  await act(async()=>button(language==='en'?'Add items':'Добавить позиции').click());
  assert.equal(closed,0); assert.equal(requests.length,1);assert.ok(document.querySelector('.batch-entry input').disabled);
  await act(async()=>button(language==='en'?'Retry save':'Повторить сохранение').click());
  assert.equal(closed,1);assert.equal(requests[0].request_id,requests[1].request_id);assert.equal(requests[1].rows[1].quantity,'140.00');
  await act(async()=>root.unmount());
 }
 localStorage.setItem('wallpanels.ui-language','en');
 const aiRoot=createRoot(document.getElementById('root'));let aiCalls=0,saveCalls=0,releaseAI;
 const aiResult={rows:[{name:'Cabinets',section:'General',quantity:'2.00',unit:'LF',unit_price:'10.00',total_price:'20.00',source:'Cabinets two LF at 10, total 20'}]};
 await act(async()=>aiRoot.render(h(LanguageProvider,null,h(ManualBatch,{onBusy:()=>{},onClose:()=>{},onAdd:async()=>saveCalls++,onParse:async()=>{aiCalls++;if(aiCalls===1)throw new Error('AI unavailable');return await new Promise(resolve=>releaseAI=()=>resolve(aiResult));}}))));
 const aiButton=text=>[...document.querySelectorAll('button')].find(b=>b.textContent===text);
 await act(async()=>aiButton('Paste list').click());
 const pasted='Cabinets two LF at 10, total 20';
 await act(async()=>{const el=document.querySelector('textarea');Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set.call(el,pasted);el.dispatchEvent(new Event('input',{bubbles:true}));});
 await act(async()=>aiButton('Parse with AI').click());
 assert.equal(document.querySelector('textarea').value,pasted);assert.equal(saveCalls,0);
 await act(async()=>aiButton('Parse with AI').click());
 assert.equal(document.querySelector('textarea').disabled,true);assert.equal(aiButton('Add items').disabled,true);assert.equal(aiButton('Cancel').disabled,true);
 await act(async()=>releaseAI());
 assert.equal(document.querySelector('.batch-entry input').value,'Cabinets');assert.equal(saveCalls,0);
 await act(async()=>aiButton('Add items').click());assert.equal(saveCalls,0);
 await act(async()=>document.querySelector('.batch-review input[type=checkbox]').click());
 await act(async()=>aiButton('Add items').click());assert.equal(saveCalls,1);
 await act(async()=>aiRoot.unmount());
 console.log('Manual batch: parser, decimal arithmetic, RU/EN editing, ordering and idempotent retry passed');
} finally {await rm(dir,{recursive:true,force:true});dom.window.close();}
