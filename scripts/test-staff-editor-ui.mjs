/** Exercise the real editor state with a synthetic canvas and transport. */
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {JSDOM} from 'jsdom';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost:5190'});
for(const k of ['window','document','HTMLElement','HTMLInputElement','HTMLTextAreaElement','Event','MouseEvent','Node','localStorage'])globalThis[k]=dom.window[k];
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
globalThis.requestAnimationFrame=fn=>setTimeout(()=>fn(performance.now()),1);globalThis.cancelAnimationFrame=clearTimeout;
window.matchMedia=()=>({matches:true});
const dir=await mkdtemp(resolve('.local/staff-editor-ui-'));
try{
 const bundle=await build({stdin:{contents:`export{default as Graph}from'./apps/frontend/src/components/staff/StaffGraph';export{NoticeProvider}from'./apps/frontend/src/components/ui';export{QueryClient,QueryClientProvider}from'@tanstack/react-query';export{createElement,act}from'react';export{createRoot}from'react-dom/client';`,resolveDir:process.cwd(),loader:'tsx'},bundle:true,packages:'external',format:'esm',platform:'node',jsx:'automatic',write:false,loader:{'.css':'empty'},define:{'import.meta.env.VITE_API_ORIGIN':'""'},plugins:[{name:'canvas-events',setup(b){b.onResolve({filter:/\.css$/},()=>({path:'css',namespace:'blank'}));b.onLoad({filter:/.*/,namespace:'blank'},()=>({contents:'',loader:'js'}));b.onResolve({filter:/^@xyflow\/react$/},()=>({path:'canvas',namespace:'stub'}));b.onLoad({filter:/.*/,namespace:'stub'},()=>({resolveDir:process.cwd(),loader:'tsx',contents:`export function ReactFlow(p){globalThis.editorCanvas=p;return <div>{p.children}</div>};export function BaseEdge(){return null};export function Handle(){return null};export function Background(){return null};export function Controls(){return null};export function MiniMap(){return null};export const Position={Bottom:'bottom',Top:'top'};export const MarkerType={ArrowClosed:'arrow'};export const BackgroundVariant={Lines:'lines',Dots:'dots'};export const getSmoothStepPath=()=>['M0,0'];export const applyNodeChanges=(_,ns)=>ns;`}));}}]});
 await writeFile(resolve(dir,'editor.mjs'),bundle.outputFiles[0].contents);
 const {Graph,NoticeProvider,QueryClient,QueryClientProvider,createElement:h,act,createRoot}=await import(pathToFileURL(resolve(dir,'editor.mjs')));
 for(const ru of [false,true]){
  const rows=[{id:'a',name:'CEO',manager_id:null},{id:'b',name:'Manager',manager_id:'a'},{id:'c',name:'Staff',manager_id:'b'}].map(p=>({...p,title:'Position',department:'Team',status:'active',version:1,fields:{},links:{}}));
  let config={version:0,extra_edges:[],orders:{},updated_by:'',updated_at:null},conflict=false,writes=[];
  globalThis.fetch=async(_path,opts={})=>{if(opts.method==='PUT'){const body=JSON.parse(opts.body);writes.push(body);if(conflict)return new Response(JSON.stringify({detail:'Conflict'}),{status:409,headers:{'Content-Type':'application/json'}});config={...config,...body,version:config.version+1};}return new Response(JSON.stringify(config),{headers:{'Content-Type':'application/json'}});};
  const client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0}}}),root=createRoot(document.getElementById('root'));
  const settle=async()=>{for(let i=0;i<4;i++)await act(async()=>new Promise(r=>setTimeout(r,10)));};
  const button=(en,r)=>[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===(ru?r:en)||b.getAttribute('aria-label')===(ru?r:en));
  const click=async(en,r)=>{const b=button(en,r);assert.ok(b,en);await act(async()=>b.click());await settle();};
  await act(async()=>root.render(h(QueryClientProvider,{client},h(NoticeProvider,null,h(Graph,{all:rows,people:rows,layout:'holi',ru,open:()=>{}})))));await settle();
  await click('Edit chart','Редактировать схему');await click('Additional','Доп. связь');
  await act(async()=>editorCanvas.onConnect({source:'c',target:'a'}));await settle();assert.equal(editorCanvas.edges.filter(e=>e.data.kind==='additional').length,1);
  await click('Undo chart change','Отменить действие');assert.equal(editorCanvas.edges.filter(e=>e.data.kind==='additional').length,0);
  await click('Redo chart change','Повторить действие');assert.equal(editorCanvas.edges.filter(e=>e.data.kind==='additional').length,1);
  await click('Save chart','Сохранить схему');assert.deepEqual(writes.at(-1).changes,[]);assert.deepEqual(config.extra_edges,[{source:'c',target:'a'}]);
  await click('Edit chart','Редактировать схему');await click('Reporting','Подчинение');assert.equal(editorCanvas.isValidConnection({source:'c',target:'a'}),false);
  await act(async()=>editorCanvas.onConnect({source:'a',target:'c'}));await settle();
  conflict=true;await click('Save chart','Сохранить схему');assert.ok(button('Save chart','Сохранить схему'));assert.equal(button('Save chart','Сохранить схему').disabled,false);assert.ok(document.body.textContent.includes(ru?'Черновик оставлен':'draft is preserved'));assert.deepEqual(writes.at(-1).changes,[{id:'c',version:1,manager_id:'a'}]);
  await click('Cancel','Отмена');conflict=false;
  await click('Edit chart','Редактировать схему');
  const extra=editorCanvas.edges.find(e=>e.data.kind==='additional');await act(async()=>editorCanvas.onEdgeClick({stopPropagation(){}},extra));await settle();await click('Delete connection','Удалить связь');await click('Save chart','Сохранить схему');assert.deepEqual(config.extra_edges,[]);assert.equal(rows.length,3);
  await act(async()=>root.unmount());client.clear();document.getElementById('root').innerHTML='';
 }
 console.log('Staff editor UI: EN/RU edit, extra/reporting links, cycles, undo/redo, atomic payload, 409 draft retention, cancel and connection deletion without employee deletion.');
}finally{await rm(dir,{recursive:true,force:true});}
