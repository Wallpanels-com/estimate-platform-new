import fs from 'node:fs';
import assert from 'node:assert/strict';
import { calculateRoom } from '../apps/frontend/src/lib/quickEstimate.ts';
const fixtures=JSON.parse(fs.readFileSync(new URL('../tests/quick-legacy-fixtures.json',import.meta.url),'utf8'));
for(const fixture of fixtures) assert.deepEqual(calculateRoom(fixture.room),fixture.expected,`${fixture.room.room_type} width=${fixture.room.width_ft}`);
console.log(`${fixtures.length} Quick Estimate parity fixtures passed against the original compiled frontend.`);
