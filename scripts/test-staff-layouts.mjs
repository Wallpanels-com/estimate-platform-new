import assert from 'node:assert/strict';
import {build} from 'esbuild';
const bundle=await build({entryPoints:['apps/frontend/src/lib/staff.ts'],bundle:true,write:false,format:'esm',platform:'node'});
const {staffPositions,reportingParents,STAFF_WIDTH:W,STAFF_HEIGHT:H}=await import('data:text/javascript;base64,'+Buffer.from(bundle.outputFiles[0].text).toString('base64'));
const layouts=['tree','horizontal','orbit','departments','terraces'];
for(const count of [1,3,45,118]) {
 const all=Array.from({length:count},(_,i)=>({id:String(i),name:'Person '+i,title:'Position',department:'Department '+i%7,status:i%3===0?'paused':'active',manager_id:i?String(Math.floor((i-1)/4)):null}));
 for(const people of [all,all.filter(p=>p.status==='active'),all.filter(p=>p.department==='Department 2')]) {
  const parents=reportingParents(people,all);
  for(const layout of layouts) {
   const pos=staffPositions(people,parents,layout);
   assert.equal(pos.size,people.length);
   for(let i=0;i<people.length;i++)for(let j=i+1;j<people.length;j++) {
    const a=pos.get(people[i].id),b=pos.get(people[j].id);
    assert.ok(Number.isFinite(a.x)&&Number.isFinite(a.y));
    assert.ok(Math.abs(a.x-b.x)>=W||Math.abs(a.y-b.y)>=H,`${layout}: overlapping ${i},${j} (${count})`);
   }
  }
 }
}
const data=[{id:'a',manager_id:null},{id:'b',manager_id:'a'},{id:'c',manager_id:'b'}];
assert.equal(reportingParents([data[0],data[2]],data).get('c'),'a');
console.log('Staff layouts: 5 styles × 4 roster sizes × 3 filters; no overlapping cards; filtered reporting lines verified.');
