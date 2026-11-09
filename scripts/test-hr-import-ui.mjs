/** Synthetic import UI only. No provided workbook, real candidates or external APIs. */
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {JSDOM} from 'jsdom';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost:5190'});
for(const key of ['window','document','HTMLElement','HTMLInputElement','HTMLDialogElement','Event','MouseEvent','Node','FormData','File','localStorage'])globalThis[key]=dom.window[key];
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;window.matchMedia=()=>({matches:true});
HTMLDialogElement.prototype.showModal=function(){this.open=true};HTMLDialogElement.prototype.close=function(){this.open=false};
const folder=await mkdtemp(resolve('.local/import-ui-'));
try{
 const bundle=await build({stdin:{contents:`export{default as CandidateImport}from'./apps/frontend/src/components/CandidateImport';export{LanguageProvider}from'./apps/frontend/src/lib/i18n';export{createElement,act}from'react';export{createRoot}from'react-dom/client';`,resolveDir:process.cwd(),loader:'tsx'},bundle:true,packages:'external',platform:'node',format:'esm',jsx:'automatic',write:false,define:{'import.meta.env.VITE_API_ORIGIN':'""'}});
 await writeFile(resolve(folder,'app.mjs'),bundle.outputFiles[0].contents);
 const{CandidateImport,LanguageProvider,createElement:h,act,createRoot}=await import(pathToFileURL(resolve(folder,'app.mjs')));
 const sheets=[{name:'English leads',columns:['id','first_name','email','phone','Experience?','Tools?'],count:3,mapping:{name:'first_name',email:'email',phone:'phone'},answer_columns:['Experience?','Tools?'],technical_columns:['id'],sample:[{first_name:'Example',email:'example@example.com','Experience?':'5 years','Tools?':'CAD'}]},{name:'Українські заявки',columns:['campaign_id','ім’я','телефон','Креслення?'],count:2,mapping:{name:'ім’я',email:'',phone:'телефон'},answer_columns:['Креслення?'],technical_columns:['campaign_id'],sample:[{'ім’я':'Example 2','Креслення?':'Так'}]}];
 for(const language of ['en','ru']){
  localStorage.setItem('wallpanels.ui-language',language);
  const requests=[];let done=null;
  globalThis.fetch=async(path,options={})=>{
   let result;
   if(path.endsWith('/imports'))result={id:'batch',sheets};
   else if(path.endsWith('/preview')||path.endsWith('/confirm')){
    const body=JSON.parse(options.body);requests.push({path,body});
    result={added:4,duplicates:1,invalid:0,test_rows:0,sample:[{name:'Example',email:'example@example.com',phone:'','answers':{'Experience?':'5 years'}}]};
   }else throw Error('Unexpected request: '+path);
   return new Response(JSON.stringify(result),{headers:{'Content-Type':'application/json'}});
  };
  const root=createRoot(document.getElementById('root'));
  const settle=async()=>{for(let i=0;i<5;i++)await act(async()=>new Promise(r=>setTimeout(r,10)))};
  const button=label=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===label);
  const click=async label=>{assert.ok(button(label),label);await act(async()=>button(label).click());await settle()};
  const checkbox=label=>[...document.querySelectorAll('label')].find(l=>l.textContent.includes(label))?.querySelector('input[type="checkbox"]');
  await act(async()=>root.render(h(LanguageProvider,null,h(CandidateImport,{vacancy:{id:'vacancy',name:'Example vacancy'},onClose:()=>{},onDone:r=>{done=r}}))));
  const input=document.querySelector('input[type="file"]');Object.defineProperty(input,'files',{value:[new File(['synthetic'],'example.xlsx')]});
  await act(async()=>input.dispatchEvent(new Event('change',{bubbles:true})));await settle();
  assert.ok(checkbox('English leads').checked&&checkbox('Українські заявки').checked);
  assert.equal(document.querySelectorAll('.hr-import-contact-grid .field').length,3);
  assert.ok(!document.querySelector('.hr-import-questions').textContent.includes('campaign_id'));
  await act(async()=>checkbox('Tools?').click());await settle();
  await click('Українські заявки');
  assert.ok(checkbox('Креслення?').checked);
  await act(async()=>checkbox('Креслення?').click());await settle();
  await act(async()=>checkbox('Українські заявки').click());await settle();
  await click(language==='ru'?'Проверить импорт':'Check import');
  assert.equal(requests.at(-1).body.sheets.length,1);
  assert.deepEqual(requests.at(-1).body.sheets[0].answer_columns,['Experience?']);
  assert.equal(done,null);assert.ok(document.querySelector('.hr-import-sample').textContent.includes('5 years'));
  await click(language==='ru'?'Изменить настройки импорта':'Edit import settings');
  await act(async()=>checkbox('Українські заявки').click());await settle();
  await click(language==='ru'?'Проверить импорт':'Check import');
  assert.equal(requests.at(-1).body.sheets.length,2);
  assert.deepEqual(requests.at(-1).body.sheets[1].answer_columns,[]);
  const preview=structuredClone(requests.at(-1).body);
  await click(language==='ru'?'Подтвердить импорт':'Confirm import');
  assert.deepEqual(requests.at(-1).body,preview);assert.equal(done.added,4);
  assert.equal(requests.filter(r=>r.path.endsWith('/confirm')).length,1);
  await act(async()=>root.unmount());document.getElementById('root').innerHTML='';
 }
 console.log('Import UI EN/RU passed: multiple sheets, independent questions, metadata exclusion, editable preview and explicit confirmation; no real imports or AI calls.');
}finally{await rm(folder,{recursive:true,force:true})}
