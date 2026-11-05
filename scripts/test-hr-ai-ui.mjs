/** Synthetic AI panel: no external AI, credentials or real HR records. */
import assert from 'node:assert/strict';
import { build } from 'esbuild';
import { JSDOM } from 'jsdom';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const dom = new JSDOM('<div id="root"></div>', {url:'http://localhost'});
for (const key of ['window','document','HTMLElement','HTMLInputElement','HTMLTextAreaElement','Event','MouseEvent','Node','FormData','localStorage']) globalThis[key]=dom.window[key];
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
const dir=await mkdtemp(resolve('.local/hr-ai-ui-'));
try {
 const b=await build({stdin:{contents:`export{default as CandidateAI}from'./apps/frontend/src/components/CandidateAI';export{outreachHtml,copyOutreach}from'./apps/frontend/src/lib/outreachRich';export{loadCandidateReview}from'./apps/frontend/src/lib/hrReview';export{LanguageProvider}from'./apps/frontend/src/lib/i18n';export{NoticeProvider}from'./apps/frontend/src/components/ui';export{QueryClient,QueryClientProvider}from'@tanstack/react-query';export{createElement,act}from'react';export{createRoot}from'react-dom/client';`,resolveDir:process.cwd(),loader:'tsx'},bundle:true,packages:'external',platform:'node',format:'esm',jsx:'automatic',write:false,define:{'import.meta.env.VITE_API_ORIGIN':'""'}});
 await writeFile(resolve(dir,'app.mjs'),b.outputFiles[0].contents);
 const {CandidateAI,outreachHtml,copyOutreach,loadCandidateReview,LanguageProvider,NoticeProvider,QueryClient,QueryClientProvider,createElement:h,act,createRoot}=await import(pathToFileURL(resolve(dir,'app.mjs')));
 assert.ok(outreachHtml('<script>alert(1)</script>').includes('&lt;script&gt;'));
 assert.ok(!outreachHtml('<img src=x onerror=bad>').includes('<img'));
 const settle=async()=>{for(let i=0;i<5;i++)await act(async()=>new Promise(r=>setTimeout(r,10)));};
 const sample='Вітаю!\n\nПро компанію\nWallpanels.com.\n\nПро вакансію\nКоординація проєктів.\n\nНаступний крок\nНадішліть резюме.\n\nСайт: https://wallpanels.com\nInstagram: https://www.instagram.com/wallpanels_com';
 for(const lang of ['en','ru']) {
  localStorage.setItem('wallpanels.ui-language',lang);
  let review=null,writes=[],copied='',rich='';
  globalThis.ClipboardItem=class {constructor(data){this.data=data;}};
  Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{copied=text;},write:async items=>{copied=await items[0].data['text/plain'].text();rich=await items[0].data['text/html'].text();}},configurable:true});
  globalThis.fetch=async(path,options={})=>{
   const method=options.method||'GET';
   if(method==='POST') {writes.push(method);review={content:{summary:'Професійний огляд',experience:'5 років',strengths:[{text:'Досвід',question:'Experience',answer:'5 years'}],gaps:[],interview_questions:['Які проєкти?'],message_uk:sample},message_draft:sample,created_by:'Example',created_at:'2026-11-05T12:00:00Z',updated_at:'v1',stale:false};}
   if(method==='PATCH') {const body=JSON.parse(options.body);writes.push(body);assert.equal(body.expected_updated_at,'v1','Dirty draft retains original concurrency version');return new Response(JSON.stringify({detail:'Concurrent message edit'}),{status:409});}
   return new Response(JSON.stringify({enabled:true,review}),{headers:{'Content-Type':'application/json'}});
  };
  let client,root;
  async function mount() {
   client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});root=createRoot(document.getElementById('root'));
   await act(async()=>root.render(h(LanguageProvider,null,h(QueryClientProvider,{client},h(NoticeProvider,null,h(CandidateAI,{id:'synthetic'}))))));await settle();
  }
  await mount();
  assert.equal(writes.length,1,'Opening an unsaved application automatically generates once');
  assert.ok(document.body.textContent.includes('Професійний огляд'));
  assert.equal(document.querySelector('.hr-ai-heading p'),null);
  assert.equal(document.querySelectorAll('.hr-ai-heading button').length,0);
  const bold=[...document.querySelectorAll('.hr-message-preview strong')].map(x=>x.textContent);
  assert.deepEqual(bold,['Вітаю!','Про компанію','Про вакансію','Наступний крок','Сайт:','Instagram:']);
  await act(async()=>root.unmount());client.clear();await mount();
  assert.equal(writes.length,1,'Reopening in a fresh client reuses the review persisted on the server');
  const button=text=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
  await act(async()=>button(lang==='ru'?'Скопировать сообщение':'Copy message').click());
  assert.equal(copied,sample);assert.ok(rich.includes('<strong>Наступний крок</strong>'));assert.ok(rich.includes('<strong>Instagram:</strong>'));
  await act(async()=>button(lang==='ru'?'Редактировать текст':'Edit message').click());
  const input=document.querySelector('textarea');
  await act(async()=>{Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,'Відредагований чернетковий текст');input.dispatchEvent(new Event('input',{bubbles:true}));});
  await act(async()=>client.setQueryData(['hr-ai','synthetic'],{enabled:true,review:{...review,updated_at:'v2',message_draft:'Other employee change'}}));
  await act(async()=>button(lang==='ru'?'Сохранить сообщение':'Save message').click());await settle();
  assert.ok(document.body.textContent.includes('Concurrent message edit'));
  assert.equal(input.value,'Відредагований чернетковий текст','Conflict does not discard draft');
  await act(async()=>root.unmount());client.clear();
  // Clipboard clients that reject rich text still get readable plain text.
  Object.defineProperty(navigator,'clipboard',{value:{write:async()=>{throw Error('unsupported');},writeText:async text=>{copied=text;}},configurable:true});
  assert.equal(await copyOutreach(sample),'plain');assert.equal(copied,sample);
 }
 // A second user/tab waits for the already-running review with GETs, never a second POST.
 let gets=0,posts=0;
 const complete={enabled:true,review:{stale:false}};
 globalThis.fetch=async(_path,options={})=>{
  if(options.method==='POST'){posts++;return new Response(JSON.stringify({detail:'AI review is already being prepared. Reopen the card shortly.'}),{status:409});}
  gets++;return new Response(JSON.stringify(gets===1?{enabled:true,review:null}:complete));
 };
 assert.deepEqual(await loadCandidateReview('concurrent'),complete);assert.equal(posts,1);assert.equal(gets,2);
 console.log('HR AI UI passed: automatic generation, saved reuse after reopen, bold preview/rich clipboard, fallback, concurrent request reuse, EN/RU and edit-conflict preservation.');
} finally {await rm(dir,{recursive:true,force:true});}
