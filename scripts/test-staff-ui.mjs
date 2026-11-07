/** Synthetic Staff UX and private gate; no site or employee workbook access. */
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {JSDOM} from 'jsdom';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost:5190'});
for(const k of ['window','document','HTMLElement','HTMLInputElement','HTMLDialogElement','Event','MouseEvent','Node','FormData','localStorage'])globalThis[k]=dom.window[k];
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
HTMLDialogElement.prototype.showModal=function(){this.open=true;};HTMLDialogElement.prototype.close=function(){this.open=false;};
const dir=await mkdtemp(resolve('.local/staff-ui-'));
try {
 const bundle=await build({stdin:{contents:`export{default as Staff}from'./apps/frontend/src/pages/Staff';export{LanguageProvider}from'./apps/frontend/src/lib/i18n';export{NoticeProvider}from'./apps/frontend/src/components/ui';export{QueryClient,QueryClientProvider}from'@tanstack/react-query';export{MemoryRouter,Routes,Route}from'react-router-dom';export{createElement,act}from'react';export{createRoot}from'react-dom/client';`,resolveDir:process.cwd(),loader:'tsx'},bundle:true,packages:'external',format:'esm',platform:'node',jsx:'automatic',write:false,loader:{'.css':'empty'},define:{'import.meta.env.VITE_API_ORIGIN':'""'},plugins:[{name:'synthetic-auth-and-canvas',setup(build){build.onLoad({filter:/\/lib\/auth.tsx$/},()=>({contents:'export const useAuth=()=>({user:{can_manage_access:globalThis.staffOwner,page_access:globalThis.staffPages}});',loader:'tsx'}));build.onLoad({filter:/StaffGraph.tsx$/},()=>({contents:'export default function Graph({people,open}){return <div data-testid="graph">{people.map(p=><button key={p.id} onClick={()=>open(p)}>{p.name}</button>)}</div>}',loader:'tsx'}));}}]});
 await writeFile(resolve(dir,'app.mjs'),bundle.outputFiles[0].contents);
 const {Staff,LanguageProvider,NoticeProvider,QueryClient,QueryClientProvider,MemoryRouter,Routes,Route,createElement:h,act,createRoot}=await import(pathToFileURL(resolve(dir,'app.mjs')));
 for(const language of ['en','ru']) {
  localStorage.setItem('wallpanels.ui-language',language);globalThis.staffOwner=false;globalThis.staffPages=['hr'];window.matchMedia=()=>({matches:true});
  const ru=language==='ru';let reads=0,writes=[],failSave=false,historyReads=0,copied='';
  Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async v=>{copied=v}}});
  let rows=Array.from({length:24},(_,i)=>({id:'person-'+i,name:'Person '+String(i).padStart(2,'0'),title:'Role',department:'Sales',status:i<22?'active':'paused',manager_id:i?'person-0':null,fields:{F:'@staff_name\n+15550100000',H:'UA',K:'person@example.com\nPayPal - billing@example.com\nPRIVATE IBAN',M:'Link',N:'Original note',O:'+15550101111 Mother Anna\n+15550102222 Brother Max',P:'Additional note',AA:'Unknown source column'},links:{K:'mailto:person@example.com',M:'https://example.com/document'},source_row:i+2,source_sheet:'Main',version:1,updated_by:'Owner',updated_at:'2026-11-06T12:00:00Z'}));
  globalThis.fetch=async(path,opts={})=>{
   let result;
   if(path.endsWith('/hr/staff')){reads++;result={items:rows,columns:{F:['Contact','Контакт'],K:['Email','Email'],O:['Additional information · O','Дополнительные сведения · O']}};}
   else if(path.endsWith('/history')){historyReads++;result=[];}
   else if(opts.method==='PATCH') {if(failSave)return new Response(JSON.stringify({detail:'Conflict: employee updated by another user'}),{status:409,headers:{'Content-Type':'application/json'}});const body=JSON.parse(opts.body);writes.push(body);rows=rows.map(p=>path.endsWith('/'+p.id)?{...p,...body,version:p.version+1}:p);result=rows.find(p=>path.endsWith('/'+p.id));}
   else throw Error('Unexpected synthetic URL '+path);
   return new Response(JSON.stringify(result),{headers:{'Content-Type':'application/json'}});
  };
  const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});const root=createRoot(document.getElementById('root'));
  const settle=async()=>{for(let i=0;i<5;i++)await act(async()=>new Promise(r=>setTimeout(r,10)));};
  const click=async(label)=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===label||b.getAttribute('aria-label')===label);assert.ok(b,label);await act(async()=>b.click());await settle();};
  const render=()=>root.render(h(LanguageProvider,null,h(QueryClientProvider,{client},h(NoticeProvider,null,h(MemoryRouter,{initialEntries:['/hr/staff']},h(Routes,null,h(Route,{path:'/hr/staff',element:h(Staff)}),h(Route,{path:'/hr',element:h('p',null,'HR home')})))))));
  await act(async()=>render());await settle();
  assert.equal(document.querySelectorAll('tbody tr').length,20);
  assert.ok(!document.querySelector('.staff-table').textContent.includes('PRIVATE IBAN'));
  await click(ru?'Следующая страница':'Next page');assert.equal(document.querySelectorAll('tbody tr').length,2);
  await click(ru?'Предыдущая страница':'Previous page');
  await act(async()=>document.querySelector('.staff-name-button').click());await settle();
  assert.ok(document.querySelector('dialog').classList.contains('staff-card'));
  assert.ok(!document.querySelector('dialog').classList.contains('staff-card-drawer'));
  assert.equal(document.querySelector('dialog input'),null,'Profile opens in readable view mode');
  assert.equal(document.querySelectorAll('[role=tab]').length,2);
  assert.equal(historyReads,0);
  assert.equal(document.querySelector('.staff-document').href,'https://example.com/document');
  assert.equal(document.querySelectorAll('dialog a[href^="mailto:"]').length,0,'Do not show email links');
  assert.ok(document.querySelector('.staff-profile-personal').textContent.includes('Ukraine'));
  assert.ok(!document.querySelector('.staff-profile-personal').textContent.includes('Link'));
  await click(ru?'Скопировать Telegram @staff_name':'Copy Telegram @staff_name');assert.equal(copied,'@staff_name');
  await click(ru?'Скопировать телефон +15550100000':'Copy phone +15550100000');assert.equal(copied,'+15550100000');
  await click(ru?'Скопировать почту person@example.com':'Copy email person@example.com');assert.equal(copied,'person@example.com');
  await click(ru?'Скопировать почту billing@example.com':'Copy email billing@example.com');assert.equal(copied,'billing@example.com');
  await click(ru?'Скопировать телефон +15550101111':'Copy phone +15550101111');assert.equal(copied,'+15550101111');
  await click(ru?'Заметки':'Notes');
  assert.ok(document.querySelector('dialog').textContent.includes('Original note'));
  assert.ok(document.querySelector('dialog').textContent.includes('Unknown source column'));
  assert.ok(!document.querySelector('dialog').textContent.includes('Mother Anna'));
  assert.equal(document.querySelector('.staff-document'),null,'Documents are on Overview only');
  await click(ru?'Редактировать':'Edit profile');
  await click(ru?'На паузе':'Paused');
  await click(ru?'Заметки':'Notes');
  assert.equal(document.querySelector('dialog textarea').value,'Original note');
  await click(ru?'Обзор':'Overview');
  assert.equal(document.querySelector('dialog textarea[aria-label="Email и PayPal"], dialog textarea[aria-label="Email & PayPal"]').value,'person@example.com\nPayPal - billing@example.com\nPRIVATE IBAN','Raw source values preserved');
  const docInput=document.querySelector('dialog input[aria-label="Ссылка на документы"], dialog input[aria-label="Document URL"]');
  for(const value of ['h','https://example.com/document']) {
    await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(docInput,value);docInput.dispatchEvent(new Event('input',{bubbles:true}));});
    assert.equal(docInput.value,value,'URL drafts must remain editable before valid');
  }
  await act(async()=>document.querySelector('dialog form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));await settle();
  assert.equal(writes.length,1);assert.equal(writes[0].status,'paused');assert.equal(writes[0].fields.O,'+15550101111 Mother Anna\n+15550102222 Brother Max');assert.equal(writes[0].fields.M,'Link');assert.equal(writes[0].fields.AA,'Unknown source column');assert.equal(writes[0].links.K,'mailto:person@example.com');assert.equal(writes[0].version,1);assert.equal(writes[0].links.M,'https://example.com/document');
  assert.equal(document.querySelector('dialog'),null);
  await act(async()=>document.querySelector('.staff-name-button').click());await settle();
  await click(ru?'Редактировать':'Edit profile');
  const name=document.querySelector('dialog input[required]');
  await act(async()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(name,'Updated draft');name.dispatchEvent(new Event('input',{bubbles:true}));});
  window.confirm=()=>false;
  await click(ru?'Закрыть':'Close');
  assert.ok(document.querySelector('dialog'),'Dirty close can be cancelled');
  failSave=true;
  await act(async()=>document.querySelector('dialog form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));await settle();
  assert.equal(document.querySelector('dialog input[required]').value,'Updated draft','Conflict retains draft');
  assert.ok(document.querySelector('dialog').textContent.includes('Conflict'));
  window.confirm=()=>true;
  await click(ru?'Закрыть':'Close');
  assert.equal(document.querySelector('dialog'),null);
  await click(ru?'Все сотрудники24':'All employees24');
  await click(ru?'Структура':'Structure');assert.equal(document.querySelectorAll('.staff-style-option').length,0);
  await click(ru?'Вся команда':'Entire team');
  for(const b of document.querySelectorAll('.staff-style-option')){await act(async()=>b.click());await settle();}
  assert.equal(document.querySelectorAll('[data-testid=graph] button').length,24);
  await act(async()=>root.unmount());client.clear();document.getElementById('root').innerHTML='';
  globalThis.staffOwner=false;globalThis.staffPages=[];
  const deniedClient=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});const deniedRoot=createRoot(document.getElementById('root'));const before=reads;
  await act(async()=>deniedRoot.render(h(LanguageProvider,null,h(QueryClientProvider,{client:deniedClient},h(MemoryRouter,{initialEntries:['/hr/staff']},h(Routes,null,h(Route,{path:'/hr/staff',element:h(Staff)}),h(Route,{path:'/hr',element:h('p',null,'HR home')})))))));await settle();
  assert.equal(reads,before);assert.equal(document.querySelector('.staff-page'),null);assert.ok(document.body.textContent.includes('HR home'));
  await act(async()=>deniedRoot.unmount());deniedClient.clear();document.getElementById('root').innerHTML='';
 }
 console.log('Staff UI: EN/RU table pagination, private contacts preview, two-tab profile, one-click contacts, separate PayPal, documents in Overview, aligned source sections, raw fields/links, no history requests, status save, conflict/dirty draft retention, single Team spaces view, HR staff access and no-HR gate without staff fetch.');
} finally {await rm(dir,{recursive:true,force:true});}
