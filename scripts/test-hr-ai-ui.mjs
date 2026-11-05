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
 const b=await build({stdin:{contents:`export{default as CandidateAI}from'./apps/frontend/src/components/CandidateAI';export{LanguageProvider}from'./apps/frontend/src/lib/i18n';export{NoticeProvider}from'./apps/frontend/src/components/ui';export{QueryClient,QueryClientProvider}from'@tanstack/react-query';export{createElement,act}from'react';export{createRoot}from'react-dom/client';`,resolveDir:process.cwd(),loader:'tsx'},bundle:true,packages:'external',platform:'node',format:'esm',jsx:'automatic',write:false,define:{'import.meta.env.VITE_API_ORIGIN':'""'}});
 await writeFile(resolve(dir,'app.mjs'),b.outputFiles[0].contents);
 const {CandidateAI,LanguageProvider,NoticeProvider,QueryClient,QueryClientProvider,createElement:h,act,createRoot}=await import(pathToFileURL(resolve(dir,'app.mjs')));
 const settle=async()=>{for(let i=0;i<5;i++)await act(async()=>new Promise(r=>setTimeout(r,10)));};
 for(const lang of ['en','ru']) {
  localStorage.setItem('wallpanels.ui-language',lang);
  let review=null,writes=[],copied='';
  Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{copied=text;}},configurable:true});
  globalThis.fetch=async(path,options={})=>{
   const method=options.method||'GET';
   if(method==='POST') {writes.push(method);review={content:{summary:'Професійний огляд',experience:'5 років',strengths:[{text:'Досвід',question:'Experience',answer:'5 years'}],gaps:[],interview_questions:['Які проєкти?'],message_uk:'Вітаю! Надішліть резюме.'},message_draft:'Вітаю! Надішліть резюме.',created_by:'Example',created_at:'2026-11-05T12:00:00Z',updated_at:'v1',stale:false};}
   if(method==='PATCH') {const body=JSON.parse(options.body);writes.push(body);assert.equal(body.expected_updated_at,'v1','Dirty draft retains original concurrency version');return new Response(JSON.stringify({detail:'Concurrent message edit'}),{status:409});}
   return new Response(JSON.stringify({enabled:true,review}),{headers:{'Content-Type':'application/json'}});
  };
  const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});
  const root=createRoot(document.getElementById('root'));
  await act(async()=>root.render(h(LanguageProvider,null,h(QueryClientProvider,{client},h(NoticeProvider,null,h(CandidateAI,{id:'synthetic'}))))));await settle();
  assert.equal(writes.length,0,'Opening a card never triggers a paid generation');
  const button=text=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===text);
  await act(async()=>button(lang==='ru'?'Разобрать анкету':'Analyze application').click());await settle();
  assert.equal(writes.length,1);assert.ok(document.body.textContent.includes('Професійний огляд'));
  await act(async()=>button(lang==='ru'?'Скопировать сообщение':'Copy message').click());assert.equal(copied,review.message_draft);
  const input=document.querySelector('textarea');
  await act(async()=>{Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,'Відредагований чернетковий текст');input.dispatchEvent(new Event('input',{bubbles:true}));});
  assert.ok(button(lang==='ru'?'Обновить разбор':'Refresh review').disabled);
  await act(async()=>client.setQueryData(['hr-ai','synthetic'],{enabled:true,review:{...review,updated_at:'v2',message_draft:'Other employee change'}}));
  await act(async()=>button(lang==='ru'?'Сохранить сообщение':'Save message').click());await settle();
  assert.ok(document.body.textContent.includes('Concurrent message edit'));
  assert.equal(input.value,'Відредагований чернетковий текст','Conflict does not discard draft');
  await act(async()=>root.unmount());client.clear();
 }
 console.log('HR AI UI passed: EN/RU on-demand generation, saved result, copy, dirty-state guard and concurrent-edit protection.');
} finally {await rm(dir,{recursive:true,force:true});}
