import assert from 'node:assert/strict';
import { build } from 'esbuild';
const result = await build({entryPoints:['apps/frontend/src/lib/staffHierarchy.ts'],bundle:true,format:'esm',platform:'node',write:false});
const {staffHierarchy,isStaffFounder}=await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`);
const person=(id,department,manager_id=null)=>({id,name:id,department,manager_id,title:'',status:'active'});
const people=[person('owner-1','Founders'),person('owner-2','Founders'),person('coo','Management','owner-1'),person('sales-lead','Sales','coo'),person('salesperson','Sales','sales-lead'),person('designer','Design','coo'),person('partner','Partners','owner-1')];
const original=JSON.stringify(people);
function ids(tree){const result=tree.founders.map(p=>p.id);for(const group of tree.departments){const visit=p=>{result.push(p.id);for(const c of group.children.get(p.id)||[])visit(c);};group.roots.forEach(visit);}return result;}
const tree=staffHierarchy(people);
assert.deepEqual(tree.founders.map(p=>p.id),['owner-1','owner-2']);
assert.ok(people.filter(isStaffFounder).every(p=>!p.manager_id));
assert.deepEqual(tree.departments.map(g=>g.name),['Management','Sales','Design','Partners']);
assert.deepEqual(tree.departments[1].children.get('sales-lead').map(p=>p.id),['salesperson']);
assert.deepEqual(ids(tree).sort(),people.map(p=>p.id).sort());
assert.deepEqual(ids(staffHierarchy(people.filter(p=>p.id==='salesperson'))),['salesperson'],'Filtering out a manager must not hide the report');
const cycle=[person('a','Design','b'),person('b','Design','a'),person('c','Design','b'),person('orphan','HR','missing')];
assert.deepEqual(ids(staffHierarchy(cycle)).sort(),cycle.map(p=>p.id).sort(),'Cycles and missing managers must not lose or repeat staff');
assert.equal(JSON.stringify(people),original,'Viewing the hierarchy must not mutate source data');
console.log('Department hierarchy: both founders, ordered departments, reporting branches, filtered/missing managers, cycles, each person once, immutable source.');
