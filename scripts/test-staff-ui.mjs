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
 const bundle=await build({stdin:{contents:`export{default as Staff}from'./apps/frontend/src/pages/Staff';export{LanguageProvider}from'./apps/frontend/src/lib/i18n';export{NoticeProvider}from'./apps/frontend/src/components/ui';export{QueryClient,QueryClientProvider}from'@tanstack/react-query';export{MemoryRouter,Routes,Route}from'react-router-dom';export{createElement,act}from'react';export{createRoot}from'react-dom/client';`,resolveDir:process.cwd(),loader:'tsx'},bundle:true,packages:'external',format:'esm',platform:'node',jsx:'automatic',write:false,loader:{'.css':'empty'},define:{'import.meta.env.VITE_API_ORIGIN':'""'},plugins:[{name:'synthetic-auth-and-canvas',setup(build){build.onLoad({filter:/\/lib\/auth.tsx$/},()=>({contents:'export const useAuth=()=>({user:{can_manage_access:globalThis.staffOwner}});',loader:'tsx'}));build.onLoad({filter:/StaffGraph.tsx$/},()=>({contents:'export default function Graph({people,open}){return <div data-testid="graph">{people.map(p=><button key={p.id} onClick={()=>open(p)}>{p.name}</button>)}</div>}',loader:'tsx'}));}}]});
 await writeFile(resolve(dir,'app.mjs'),bundle.outputFiles[0].contents);
 const {Staff,LanguageProvider,NoticeProvider,QueryClient,QueryClientProvider,MemoryRouter,Routes,Route,createElement:h,act,createRoot}=await import(pathToFileURL(resolve(dir,'app.mjs')));
 for(const language of ['en','ru']) {
  localStorage.setItem('wallpanels.ui-language',language);globalThis.staffOwner=true;
  const ru=language==='ru';let reads=0,writes=[];
  let rows=Array.from({length:24},(_,i)=>({id:'person-'+i,name:'Person '+String(i).padStart(2,'0'),title:'Role',department:'Sales',status:i<22?'active':'paused',manager_id:i?'person-0':null,fields:{F:'+15550100000',K:'payroll person@example.com\nPRIVATE IBAN',M:'Document label',O:'Original additional information'},links:{M:'https://example.com/document'},source_row:i+2,source_sheet:'Main',version:1,updated_by:'Owner',updated_at:'2026-11-06T12:00:00Z'}));
  globalThis.fetch=async(path,opts={})=>{
   let result;
   if(path.endsWith('/hr/staff')){reads++;result={items:rows,columns:{F:['Contact','Контакт'],K:['Email','Email'],O:['Additional information · O','Дополнительные сведения · O']}};}
   else if(path.endsWith('/history'))result=[];
   else if(opts.method==='PATCH') {const body=JSON.parse(opts.body);writes.push(body);rows=rows.map(p=>path.endsWith('/'+p.id)?{...p,...body,version:p.version+1}:p);result=rows.find(p=>path.endsWith('/'+p.id));}
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
  assert.ok(document.querySelector('dialog').textContent.includes('Original additional information'));
  assert.equal(document.querySelector('.staff-document').href,'https://example.com/document');
  await click(ru?'На паузе':'Paused');
  await act(async()=>document.querySelector('dialog form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));await settle();
  assert.equal(writes.length,1);assert.equal(writes[0].status,'paused');assert.equal(writes[0].fields.O,'Original additional information');assert.equal(writes[0].version,1);assert.equal(writes[0].links.M,'https://example.com/document');
  assert.equal(document.querySelector('dialog'),null);
  await click(ru?'24Все сотрудники':'24All employees');
  await click(ru?'Структура':'Structure');assert.equal(document.querySelectorAll('.staff-style-option').length,5);
  await click(ru?'Вся команда':'Entire team');
  for(const b of document.querySelectorAll('.staff-style-option')){await act(async()=>b.click());await settle();}
  assert.equal(document.querySelectorAll('[data-testid=graph] button').length,24);
  await act(async()=>root.unmount());client.clear();document.getElementById('root').innerHTML='';
  globalThis.staffOwner=false;
  const deniedClient=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}});const deniedRoot=createRoot(document.getElementById('root'));const before=reads;
  await act(async()=>deniedRoot.render(h(LanguageProvider,null,h(QueryClientProvider,{client:deniedClient},h(MemoryRouter,{initialEntries:['/hr/staff']},h(Routes,null,h(Route,{path:'/hr/staff',element:h(Staff)}),h(Route,{path:'/hr',element:h('p',null,'HR home')})))))));await settle();
  assert.equal(reads,before);assert.equal(document.querySelector('.staff-page'),null);assert.ok(document.body.textContent.includes('HR home'));
  await act(async()=>deniedRoot.unmount());deniedClient.clear();document.getElementById('root').innerHTML='';
 }
 console.log('Staff UI: EN/RU table pagination, private contacts preview, complete card, preserved fields/links, status save, 5 styles and non-owner gate without staff fetch.');
} finally {await rm(dir,{recursive:true,force:true});}
