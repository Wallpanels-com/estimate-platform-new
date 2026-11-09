import assert from 'node:assert/strict';
import {build} from 'esbuild';
const out=await build({stdin:{contents:"export*from'./apps/frontend/src/lib/staffChart';export*from'./apps/frontend/src/lib/staff';export*from'./apps/frontend/src/lib/staffReferenceLayouts';",resolveDir:process.cwd(),loader:'ts'},bundle:true,write:false,format:'esm',platform:'node'});
const m=await import('data:text/javascript;base64,'+Buffer.from(out.outputFiles[0].text).toString('base64'));
const people=[{id:'a',name:'CEO',manager_id:null,version:1},{id:'b',name:'Manager',manager_id:'a',version:2},{id:'c',name:'Employee',manager_id:'b',version:3},{id:'d',name:'Another',manager_id:'b',version:1}];
const baseline=m.chartDraft(people,{extra_edges:[],orders:{}});
assert.equal(m.chartDraft(people,{extra_edges:[{source:'b',target:'c'}],orders:{}}).extra_edges.length,0);
assert.equal(m.canConnect(baseline,'c','a','reporting'),false);
assert.equal(m.canConnect(baseline,'a','a','additional'),false);
assert.equal(m.canConnect(baseline,'unknown','c','additional'),false);
assert.equal(m.canConnect(baseline,'a','c','reporting'),true);
const moved=m.connectDraft(baseline,'a','c','reporting');assert.equal(moved.managers.c,'a');assert.equal(baseline.managers.c,'b');
assert.deepEqual(m.chartChanges(moved,people),[{id:'c',version:3,manager_id:'a'}]);
const extra=m.connectDraft(baseline,'c','a','additional');assert.equal(extra.extra_edges.length,1);assert.equal(extra.managers.a,null);
assert.equal(m.canConnect(extra,'c','a','additional'),false);
assert.equal(m.removeConnection(extra,'c','a','additional').extra_edges.length,0);
assert.equal(m.removeConnection(baseline,'b','c','reporting').managers.c,null);
const reconnected=m.reconnectDraft(baseline,'b','c','a','c','reporting');assert.equal(reconnected.managers.c,'a');
assert.equal(m.reconnectDraft(baseline,'a','b','c','b','reporting'),baseline,'Invalid reconnection must keep the old link');
assert.equal(m.reconnectDraft(extra,'c','a','d','a','additional').extra_edges[0].source,'d');
const positions=new Map([['c',{x:0,y:200}],['d',{x:350,y:200}]]);
const reordered=m.reorderAfterDrop(baseline,people,people,positions,'c',{x:450,y:200},'holi');assert.equal(reordered.orders.holi.indexOf('c'),reordered.orders.holi.indexOf('d')+1);assert.deepEqual(reordered.managers,baseline.managers);
assert.equal(m.reorderAfterDrop(baseline,people,people,positions,'a',{x:900,y:900},'holi'),baseline);
for(const count of [1,3,45,118]){
 const all=Array.from({length:count},(_,i)=>({id:String(i),name:'Person '+i,title:'Position',department:i<3?'Administration':'Department '+i%7,status:i%3?'active':'paused',manager_id:i?String(Math.floor((i-1)/4)):null}));
 for(const subset of [all,all.filter(p=>p.status==='active'),all.filter(p=>p.department==='Department 2')])for(const layout of ['teams','holi','compact']){
  const parents=m.reportingParents(subset,all),scene=m.referenceScene(subset,parents,layout),geometry=m.referenceGeometry(layout);
  assert.equal(scene.positions.size,subset.length);
  for(let i=0;i<subset.length;i++)for(let j=i+1;j<subset.length;j++){
   const a=scene.positions.get(subset[i].id),b=scene.positions.get(subset[j].id);
   assert.ok(Number.isFinite(a.x)&&Number.isFinite(a.y));
   assert.ok(Math.abs(a.x-b.x)>=geometry.width||Math.abs(a.y-b.y)>=geometry.height,`${layout} ${count}: overlapping cards ${i}/${j}`);
  }
  for(const group of scene.groups)assert.ok(group.width>0&&group.height>0);
 }
}
console.log('Staff chart: primary/collaboration validation, immutable drafts, ordered drag, manager version payload and 3 reference layouts × 4 sizes × 3 filters without overlap.');
