/** Shared dialog presence: no real network, accounts or employee data. */
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {JSDOM} from 'jsdom';
import {mkdtemp,writeFile,rm} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const dom=new JSDOM('<div id="root"></div>',{url:'http://localhost'});
for(const k of ['window','document','HTMLElement','HTMLDialogElement','Event','MouseEvent','Node','localStorage'])globalThis[k]=dom.window[k];
Object.defineProperty(globalThis,'navigator',{value:dom.window.navigator,configurable:true});
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
let opens=0,closes=0,reduced=false;
window.matchMedia=()=>({matches:reduced});
HTMLDialogElement.prototype.showModal=function(){this.open=true;opens++;this.querySelector('button')?.focus();};
HTMLDialogElement.prototype.close=function(){this.open=false;closes++;};
const dir=await mkdtemp(resolve('.local/modal-motion-'));
try{
 const bundle=await build({stdin:{contents:`import{useState}from'react';import{Modal,ModalPresence}from'./apps/frontend/src/components/ui';export{act,createElement}from'react';export{createRoot}from'react-dom/client';export function Harness(){const[open,setOpen]=useState(false);globalThis.motionSet=setOpen;return <><button id="launcher" onClick={()=>setOpen(true)}>Open</button><ModalPresence>{open&&<Modal title="Profile" onClose={()=>{globalThis.dismisses++;setOpen(false)}}><form onSubmit={e=>{e.preventDefault();globalThis.submits++}}><button type="submit">Save</button><button type="button" onClick={()=>setOpen(false)}>Cancel</button></form></Modal>}</ModalPresence></>}`,resolveDir:process.cwd(),loader:'tsx'},bundle:true,packages:'external',format:'esm',platform:'node',jsx:'automatic',write:false});
 await writeFile(resolve(dir,'app.mjs'),bundle.outputFiles[0].contents);
 const{Harness,act,createElement:h,createRoot}=await import(pathToFileURL(resolve(dir,'app.mjs')));
 const root=createRoot(document.getElementById('root'));globalThis.dismisses=0;globalThis.submits=0;
 await act(async()=>root.render(h(Harness)));
 const launch=async()=>act(async()=>{document.querySelector('#launcher').focus();document.querySelector('#launcher').click()});
 const cancel=async()=>act(async()=>document.querySelector('form button[type=button]').click());
 await launch();const first=document.querySelector('dialog');assert.equal(first.open,true);assert.ok(first.getAttribute('aria-labelledby'));
 await cancel();assert.equal(document.querySelector('dialog'),first);assert.equal(first.dataset.closing,'true','Retain dialog for exit animation');
 await act(async()=>first.querySelector('form').dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));assert.equal(submits,0,'No duplicate submit while leaving');
 await act(async()=>new Promise(r=>setTimeout(r,180)));assert.equal(document.querySelector('dialog'),null);assert.equal(document.activeElement.id,'launcher','Restore focus after exit');
 await launch();await cancel();await act(async()=>motionSet(true));await act(async()=>new Promise(r=>setTimeout(r,180)));assert.ok(document.querySelector('dialog'));assert.equal(document.querySelector('dialog').dataset.closing,undefined,'Fast reopen cancels old exit timer');
 await act(async()=>{const e=new Event('cancel',{cancelable:true});document.querySelector('dialog').dispatchEvent(e);assert.equal(e.defaultPrevented,true);});assert.equal(dismisses,1,'Escape uses the normal dismiss guard');
 await act(async()=>new Promise(r=>setTimeout(r,180)));assert.equal(document.querySelector('dialog'),null);
 reduced=true;await launch();await cancel();assert.equal(document.querySelector('dialog'),null,'Reduced motion closes immediately');
 reduced=false;await launch();await cancel();await act(async()=>root.unmount());await act(async()=>new Promise(r=>setTimeout(r,180)));assert.equal(document.querySelector('dialog'),null);
 assert.equal(opens,closes);
 console.log('Modal motion: enter/exit lifecycle, focus return, Escape, reduced motion, duplicate-submit prevention, fast reopen and cleanup passed.');
}finally{await rm(dir,{recursive:true,force:true});}
